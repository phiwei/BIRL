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

1. Download source code: https://github.com/biomedia-mira/drop2
2. Install all required libraries such as ITK
3. Build following the instructions in DROP2 project readme
4. Test calling the executable `./dropreg` which should return something like::

    TODO
    Usage: dropreg2d <source> <target> <result> <paramfile> [mask]

Usage
-----

Sample run of DROP2::

    ./dropreg --mode2d
        -s S1.jpg -t HE.jpg -o S1_to_HE.nii.gz
        -l --ltype 0 --lsim 1 --llevels 32 32 32 16 16 16 --lsampling 0.2
        -n --nffd 1000 --nsim 1 --nlevels 16 16 16 8 8 8 --nlambda 0.5 --npin

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
from bm_experiments import bm_comp_perform
from bm_experiments.bm_DROP import BmDROP


class BmDROP2(BmDROP):
    """ Benchmark for DROP2
    no run test while this method requires manual installation of DROP2

    For the app installation details, see module details.

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
    #: command for executing the image registration
    COMMAND_REGISTER = '%(dropRegistration)s --mode2d \
        -s %(source)s \
        -t %(target)s \
        -o %(output)s.nii.gz \
        %(config)s'

    def _generate_regist_command(self, item):
        """ generate the registration command

        :param dict item: dictionary with registration params
        :return str|list(str): the execution commands
        """
        logging.debug('.. prepare DROP registration command')
        with open(self.params['path_config'], 'r') as fp:
            config = [l.rstrip().replace('\\', '') for l in fp.readlines()]
        config = ' '.join(config)

        path_im_ref, path_im_move, _, _ = self._get_paths(item)
        path_dir = self._get_path_reg_dir(item)

        command = self.COMMAND_REGISTER % {
            'dropRegistration': self.params['exec_DROP'],
            'source': path_im_move,
            'target': path_im_ref,
            'output': os.path.join(path_dir, 'output'),
            'config': config,
        }

        return command


# RUN by given parameters
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    arg_params, path_expt = BmDROP2.main()

    if arg_params.get('run_comp_benchmark', False):
        bm_comp_perform.main(path_expt)
