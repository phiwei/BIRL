"""
Benchmark for DROP.

DROP is a approach for image registration and motion estimation based on Markov Random Fields.

.. ref:: https://github.com/biomedia-mira/drop2

Related Publication:
Deformable Medical Image Registration: Setting the State of the Art with Discrete Methods
 Authors: Ben Glocker, Aristeidis Sotiras, Nikos Komodakis, Nikos Paragios
 Published in: Annual Review of Biomedical Engineering, Vol. 12, 2011, pp. 219-244


Installation for Linux
----------------------

1. Download executable according your operation system,
 https://www.mrf-registration.net/deformable/index.html
2. Copy/extract executables and libraries to you favourite destination
3. Install all missing libraries such as QT4 with OpenGL support
4. Test calling the executable `./dropreg2d` which should return something like::

    Usage: dropreg2d <source> <target> <result> <paramfile> [mask]

Usage
-----

To see the explanation of particular parameters see the User Manual
 http://www.mrf-registration.net/download/drop_user_guide_V1.05.pdf

Sample run::

    mkdir ./results
    python bm_experiments/bm_DROP2.py \
        -t ./data_images/pairs-imgs-lnds_histol.csv \
        -d ./data_images \
        -o ./results \
        -DROP ~/Applications/DROP2/dropreg \
        --path_config ./configs/DROP2.txt \
        --visual --unique

.. note:: experiments was tested on Ubuntu (Linux) based OS system

.. note:: This method is not optimized nor suitable for large images, so all used images
 are first scaled to be 1000x1000 pixels and then the registration is performed.
  After registration is resulting image scaled back. The landmarks are scalded accordingly.

Copyright (C) 2017-2019 Jiri Borovec <jiri.borovec@fel.cvut.cz>
"""
from __future__ import absolute_import

import os
import sys
import logging

sys.path += [os.path.abspath('.'), os.path.abspath('..')]  # Add path to root
from birl.utilities.data_io import (
    convert_image_to_mhd, convert_image_from_mhd, save_landmarks, load_landmarks, image_sizes)
from birl.benchmark import ImRegBenchmark
from bm_experiments import bm_comp_perform
from bm_experiments.bm_DROP import BmDROP


class BmDROP2(BmDROP):
    """ Benchmark for DROP2
    no run test while this method requires manual installation of DROP2

    For the app installation details, see module details.

    .. note:: DROP requires gray scale images in MHD format where pixel values
    are in range (0, 255) of uint8.

    Example
    -------
    >>> from birl.utilities.data_io import create_folder, update_path
    >>> path_out = create_folder('temp_results')
    >>> path_csv = os.path.join(update_path('data_images'), 'pairs-imgs-lnds_mix.csv')
    >>> params = {'path_table': path_csv,
    ...           'path_out': path_out,
    ...           'nb_workers': 2,
    ...           'unique': False,
    ...           'visual': True,
    ...           'exec_DROP': 'dropreg2d',
    ...           'path_config': os.path.join(update_path('configs'), 'DROP.txt')}
    >>> benchmark = BmDROP2(params)
    >>> benchmark.run()  # doctest: +SKIP
    >>> del benchmark
    >>> import shutil
    >>> shutil.rmtree(path_out, ignore_errors=True)
    """


# RUN by given parameters
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    arg_params, path_expt = BmDROP2.main()

    if arg_params.get('run_comp_benchmark', False):
        bm_comp_perform.main(path_expt)
