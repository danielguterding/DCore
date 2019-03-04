#!/usr/bin/env python
#
# DCore -- Integrated DMFT software for correlated electrons
# Copyright (C) 2017 The University of Tokyo
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
from __future__ import print_function

import argparse
import sys
import os
import shlex
import subprocess

from pytriqs.archive import HDFArchive
from .tools import launch_mpi_subprocesses

def read_dft_input_data(file, subgrp, things_to_read):
    """

    Small version of SumkDFT.read_input_from_hdf()
    Read DFT data from a HDF file and return the data as a dict.

    """

    values = {}
    with HDFArchive(file, 'r') as ar:
        if not subgrp in ar:
            raise RuntimeError("subrp " + subgrp + "does not exist in " + file + "!")
        # first read the necessary things:
        for it in things_to_read:
            values[it] = ar[subgrp][it]

    return values


class SumkDFTCompat(object):
    def __init__(self, hdf_file):

        things_to_read = ['energy_unit', 'n_k', 'k_dep_projection', 'SP', 'SO', 'charge_below', 'density_required',
                          'symm_op', 'n_shells', 'shells', 'n_corr_shells', 'corr_shells', 'use_rotations', 'rot_mat',
                          'rot_mat_time_inv', 'n_reps', 'dim_reps', 'T', 'n_orbitals', 'proj_mat', 'bz_weights',
                          'hopping',
                          'n_inequiv_shells', 'corr_to_inequiv', 'inequiv_to_corr']

        dft_data = read_dft_input_data(hdf_file, subgrp='dft_input', things_to_read=things_to_read)

        for k, v in dft_data.items():
            setattr(self, k, v)

        if self.SO != self.SP:
            raise RuntimeError("Not supported SP={} != SO={}.".format(self.SO, self.SP))


def run(model_file, work_dir, mpirun_command, params):
    """
    Runs SumKDFT by launching MPI processes.

    :param model_file: str
        HDF5 file
    :param work_dir: str
        Working directory
    :param mpirun_command: str
        Command for executing mpi programs
    :param params: dict
        Parameters for SumkDFT
    :return: dict
        results

    params contains the following parameters.
        calc_mode   : str, 'Gloc', 'dos', 'dos0', 'spaghettis' or 'momentum_distribution' (mandatory)
        mu          : float, chemical potential. If mu is not given, mu will be adjusted (optional).
        prec_mu     : float, precision of adjustment of chemical potential (optional)
        broadening  : float, broadening parameter for DOS (must be set when calc_mode = dos, dos0, spaghettis)
        mesh        : (float, float, int) real-frequency mesh (optional)

    """

    from .tools import raise_if_mpi_imported
    raise_if_mpi_imported()

    # Prepare input files
    if not os.path.exists(work_dir):
        os.makedirs(work_dir)
    with HDFArchive(work_dir + '/input.h5', 'w') as h:
        h['params'] = params

    commands = [sys.executable, "-m", "dcore.sumkdft"]
    commands.append(model_file)
    commands.append(os.path.abspath(work_dir + '/input.h5'))
    commands.append(os.path.abspath(work_dir + '/output.h5'))

    with open(work_dir + '/output', 'w') as output_file:
        launch_mpi_subprocesses(mpirun_command, commands, output_file)

    with open(work_dir + '/output', 'r') as output_file:
        for line in output_file:
            print(line, end='')

    results = {}
    with HDFArchive(os.path.abspath(work_dir + '/output.h5'), 'r') as h:
        for k in h.keys():
            results[k] = h[k]

    return results


def _main_mpi(model_hdf5_file, input_file, output_file):
    """

    Launch SumkDFT and compute chemical potential, local Green's function and density matrix
    This function depends on MPI through DFTTools.
    Do not call this from non-MPI module directly.

    """

    import pytriqs.utility.mpi as mpi

    with HDFArchive(input_file, 'r') as h:
        params = h['params']

    beta = params['beta']
    with_dc = params['with_dc']

    results = {}

    def setup_sk(sk, iwn_or_w_or_none):
        if iwn_or_w_or_none == 'iwn':
            sk.set_Sigma(params['Sigma_iw_sh'])
        elif iwn_or_w_or_none == 'w':
            sk.set_Sigma([params['Sigma_w_sh'][ish] for ish in range(sk.n_inequiv_shells)])
        elif iwn_or_w_or_none == "none":
            pass
        else:
            raise RuntimeError("Invalid iwn_or_w")

        if params['with_dc']:
            sk.set_dc(params['dc_imp'], params['dc_energ'])
        sk.set_mu(params['mu'])

    if params['calc_mode'] == 'Gloc':
        from pytriqs.applications.dft.sumk_dft import SumkDFT
        sk = SumkDFT(hdf_file=model_hdf5_file, use_dft_blocks=False, h_field=0.0)
        setup_sk(sk, 'iwn')
        if params['adjust_mu']:
            # find the chemical potential for given density
            sk.calc_mu(params['prec_mu'])
            results['mu'] = sk.chemical_potential

        # Local Green's function and Density matrix
        results['Gloc_iw_sh'] = sk.extract_G_loc(with_dc=with_dc)
        results['dm_corr_sh'] = sk.density_matrix(beta=beta)

    elif params['calc_mode'] == 'dos':
        # Compute dos
        from .sumkdft_post import SumkDFTDCorePost
        sk = SumkDFTDCorePost(hdf_file=model_hdf5_file, use_dft_blocks=False, h_field=0.0)
        setup_sk(sk, 'w')
        results['dos'], results['dosproj'], results['dosproj_orb'] = \
            sk.dos_wannier_basis(broadening=params['broadening'],
                             mesh=params['mesh'],
                             with_Sigma=True, with_dc=with_dc, save_to_file=False)

    elif params['calc_mode'] == 'dos0':
        # Compute non-interacting dos
        from .sumkdft_post import SumkDFTDCorePost
        sk = SumkDFTDCorePost(hdf_file=model_hdf5_file, use_dft_blocks=False, h_field=0.0)
        setup_sk(sk, "none")
        results['dos0'], results['dosproj0'], results['dosproj_orb0'] = \
            sk.dos_wannier_basis(broadening=params['broadening'],
                             mu=params['mu'],
                             mesh=params['mesh'],
                             with_Sigma=False, with_dc=False, save_to_file=False)

    elif params['calc_mode'] == 'spaghettis':
        # A(k, omega)
        from .sumkdft_post import SumkDFTDCorePost
        sk = SumkDFTDCorePost(hdf_file=model_hdf5_file, use_dft_blocks=False, h_field=0.0)
        setup_sk(sk, 'w')
        results['akw'] = sk.spaghettis(broadening=params['broadening'], plot_range=None, ishell=None, save_to_file=None)

    elif params['calc_mode'] == 'momentum_distribution':
        # n(k)
        from .sumkdft_post import SumkDFTDCorePost
        sk = SumkDFTDCorePost(hdf_file=model_hdf5_file, use_dft_blocks=False, h_field=0.0)
        setup_sk(sk, 'iwn')
        results['den'], results['ev0'] = \
            sk.calc_momentum_distribution(mu=params["mu"], beta=beta, with_Sigma=True, with_dc=True)

    elif params['calc_mode'] == 'bse':
        # chi0
        from dft_tools.sumk_dft_chi import SumkDFTChi
        # save div data (overwrite if data exist)
        if mpi.is_master_node():
            with HDFArchive(model_hdf5_file, 'a') as ar:
                if 'dft_input_chi' in ar:
                   del ar['dft_input_chi']
                ar.create_group('dft_input_chi')
                ar['dft_input_chi']['div'] = params['div']
        # check if IBZ and FBZ data are saved separately
        dft_data_fbz = 'dft_input'
        if mpi.is_master_node():
            with HDFArchive(model_hdf5_file, 'r') as ar:
                if 'dft_input_fbz' in ar:
                    dft_data_fbz = 'dft_input_fbz'
        dft_data_fbz = mpi.bcast(dft_data_fbz)
        sk = SumkDFTChi(hdf_file=model_hdf5_file, use_dft_blocks=False, h_field=0.0,
                        dft_data_fbz=dft_data_fbz)
        setup_sk(sk, 'iwn')
        sk.save_X0q_for_bse(list_wb=params['list_wb'],
                            n_wf_cutoff=params['n_wf_G2'],
                            qpoints_saved='quadrant',
                            h5_file=params['bse_h5_out_file'],
                            nonlocal_order_parameter=False)
    else:
        raise RuntimeError("Unknown calc_mode: " + str(params['calc_mode']))

    if mpi.is_master_node():
        with HDFArchive(output_file, 'w') as h:
            for k, v in results.items():
                h[k] = v

if __name__ == '__main__':

    try:
        parser = argparse.ArgumentParser(
            description='Internal program for launching SumkDFT. Please run this like mpirun pytriqs sumkdft.py')
        parser.add_argument('model_hdf5_file')
        parser.add_argument('input_file')
        parser.add_argument('output_file')
        args = parser.parse_args()

        _main_mpi(args.model_hdf5_file, args.input_file, args.output_file)

    except Exception as e:
        print("Unexpected error:", e)
        import traceback
        traceback.print_exc()
        sys.exit(1)
