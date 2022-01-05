# This file is part of the NIME Proceedings Analyzer (NIME PA)
# Copyright (C) 2022 Jackson Goode, Stefano Fasciani

# The NIME PA is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# The NIME PA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# If you use the NIME Proceedings Analyzer or any part of it in any program or
# publication, please acknowledge its authors by adding a reference to:

# J. Goode, S. Fasciani, A Toolkit for the Analysis of the NIME Proceedings
# Archive, submitted to 2022 International Conference on New Interfaces for
# Musical Expression, Auckland, New Zealand, 2022.

from tqdm import tqdm
import logging

notice = '\nNIME Proceedings Analyzer\n\
Copyright (C) 2022 Jackson Goode, Stefano Fasciani\n\
This program comes with ABSOLUTELY NO WARRANTY;\n\
This is free software, and you are welcome to redistribute it\n\
under certain conditions; for details check the LICENSE file.\n'

# Allows a verbose toggle to switch on/off prints to console
def init(args):
    global tprint
    global nprint
    global lprint

    logging.basicConfig(filename='./lastrun.log', level=logging.INFO)

    def tqdm_out(msg):
        # Remove formatting of display
        logging.info(' '.join(msg.strip().splitlines()))

        if args.verbose:
            tqdm.write(msg)

    def normal_out(msg):
        logging.info(msg)

        if args.verbose:
            print(msg)

    def licence_out():
        print(notice)

    tprint = tqdm_out
    nprint = normal_out
    lprint = licence_out
