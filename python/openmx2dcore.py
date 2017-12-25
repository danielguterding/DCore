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
import sys
import numpy

args = sys.argv

if len(args) != 3:
    print("\nUsage:\n")
    print("  $ openmx2dcore {HWR file} {seedname}\n")
    exit()
#
# Input
#
with open(args[1], 'r') as f:
    line = f.readline() # Skip
    #
    line = f.readline()
    itemlist = line.split()
    nwan = int(itemlist[4])
    #
    line = f.readline()
    itemlist = line.split()
    ncell = int(itemlist[4])
    #
    # Allocate
    #
    cell = numpy.zeros([ncell, 3], numpy.int_)
    eqcell = numpy.zeros(ncell, numpy.int_)
    hopping = numpy.zeros([ncell, nwan, nwan], numpy.complex_)
    #
    line = f.readline()
    line = f.readline()
    line = f.readline()
    line = f.readline()
    line = f.readline()
    line = f.readline()
    itemlist = line.split()
    efermi = float(itemlist[2])
    #
    for icell in range(ncell):
        #
        line = f.readline()
        itemlist = line.split()
        for ii in range(3): cell[icell,ii] = int(itemlist[2+ii])
        eqcell[icell] = int(itemlist[6])
        #
        for iwan in range(nwan):
            for jwan in range(nwan):
                line = f.readline()
                itemlist = line.split()
                hopping[icell, iwan, jwan] = float(itemlist[2]) + 1j * float(itemlist[3])
                hopping[icell, iwan, jwan] *= 13.60569228 * 2.0 # Hartree -> eV
#
# Output
#
with open(args[2]+"_hr.dat", 'w') as f:
    #
    print("Convert from OpenMX output. Converted to eV unit", file=f)
    print(nwan, file=f)
    print(ncell, file=f)
    for icell in range(ncell):
        if icell % 15 == 0 and icell != 0: print("", file=f)
        print("    {0}".format(eqcell[icell]), file=f, end='')
    print("", file=f)
    #
    for icell in range(ncell):
        for jwan in range(nwan):
            for iwan in range(nwan):
                print("%5d%5d%5d%5d%5d%12.6f%12.6f" % (
                    cell[icell,0], cell[icell,1], cell[icell,2], iwan+1, jwan+1,
                    numpy.real(hopping[icell,iwan,jwan]), numpy.imag(hopping[icell,iwan,jwan]), ), file=f)
