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
2. Install all required libraries such as ITK, and build following the instructions
    OR run building script `build.sh` included in the repository
3. Test calling the executable `./build/drop/apps/dropreg/dropreg` which should return something like::

    Usage: dropreg --help

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
import time
import logging

sys.path += [os.path.abspath('.'), os.path.abspath('..')]  # Add path to root
from birl.utilities.data_io import (
    convert_image_from_mhd, save_landmarks, load_landmarks, image_sizes,
    load_image, save_image, image_resize)
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
    ...           'exec_DROP': 'dropreg',
    ...           'path_config': os.path.join(update_path('configs'), 'DROP2.txt')}
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

    def _prepare_img_registration(self, item):
        """ converting the input images to gra-scale and MHD format

        :param dict item: dictionary with registration params
        :return dict: the same or updated registration info
        """
        logging.debug('.. rescaling images if needed')
        path_im_ref, path_im_move, _, _ = self._get_paths(item)
        path_reg_dir = self._get_path_reg_dir(item)

        diags = [image_sizes(p_img)[1] for p_img in (path_im_ref, path_im_move)]
        item['scaling'] = max(1, max(diags) / float(self.MAX_IMAGE_DIAGONAL))

        if item['scaling'] > 1:
            # the image is smaller then max, so nothing to do
            return item

        t_start = time.time()
        for path_img, col in [(path_im_ref, self.COL_IMAGE_REF),
                              (path_im_move, self.COL_IMAGE_MOVE)]:
            img = load_image(path_img)
            # the MHD usually require pixel value range (0, 255)
            img = image_resize(img, 1. / item['scaling'], v_range=255)
            path_img_out = os.path.join(path_reg_dir, os.path.basename(path_img))
            save_image(path_img_out, img)
            item[col + self.COL_IMAGE_EXT_TEMP] = path_img_out
        item[self.COL_TIME_CONVERT] = time.time() - t_start

        return item

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

    def _extract_warped_image_landmarks(self, item):
        """ get registration results - warped registered images and landmarks

        :param dict item: dictionary with registration params
        :return dict: paths to warped images/landmarks
        """
        # TODO

        # path_reg_dir = self._get_path_reg_dir(item)
        # _, path_im_move, path_lnds_ref, _ = self._get_paths(item)
        # # convert MHD image
        # path_img_ = convert_image_from_mhd(os.path.join(path_reg_dir, 'output.mhd'),
        #                                    scaling=item.get('scaling', 1.))
        # img_name = os.path.splitext(os.path.basename(path_im_move))[0]
        # ext_img = os.path.splitext(os.path.basename(path_img_))[1]
        # path_img_warp = path_img_.replace('output' + ext_img, img_name + ext_img)
        # shutil.move(path_img_, path_img_warp)
        #
        # # load transform and warp landmarks
        # # lnds_move = load_landmarks(path_lnds_move)
        # lnds_ref = load_landmarks(path_lnds_ref)
        # lnds_name = os.path.basename(path_lnds_ref)
        # path_lnds_warp = os.path.join(path_reg_dir, lnds_name)
        # assert lnds_ref is not None, 'missing landmarks to be transformed "%s"' % lnds_name
        #
        # # down-scale landmarks if defined
        # lnds_ref = lnds_ref / item.get('scaling', 1.)
        # # extract deformation
        # path_deform_x = os.path.join(path_reg_dir, 'output_x.mhd')
        # path_deform_y = os.path.join(path_reg_dir, 'output_y.mhd')
        # try:
        #     shift = self.extract_landmarks_shift_from_mhd(path_deform_x, path_deform_y, lnds_ref)
        # except Exception:
        #     logging.exception(path_reg_dir)
        #     shift = np.zeros(lnds_ref.shape)
        #
        # # lnds_warp = lnds_move - shift
        # lnds_warp = lnds_ref + shift
        # # upscale landmarks if defined
        # lnds_warp = lnds_warp * item.get('scaling', 1.)
        # save_landmarks(path_lnds_warp, lnds_warp)

        # return formatted results
        return {self.COL_IMAGE_MOVE_WARP: path_img_warp,
                self.COL_POINTS_REF_WARP: path_lnds_warp}


# RUN by given parameters
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    arg_params, path_expt = BmDROP2.main()

    if arg_params.get('run_comp_benchmark', False):
        bm_comp_perform.main(path_expt)
