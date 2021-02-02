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

from dcore.dcore_pre import dcore_pre
from dcore.dcore import dcore
from dcore.dcore_bse import dcore_bse
from triqs.utility.h5diff import h5diff
#
# Execute dcore_pre.py to generate test.h5
# Then Check the Diff of test.h5 and the reference output (stan_ref.h5))
#

input_ini = "square_2orb.ini"

dcore_pre(input_ini)
dcore(input_ini)
dcore_bse(input_ini)

h5diff("dmft_bse.h5", "dmft_bse.h5.ref")
