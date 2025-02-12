"""
Evaluating passed experiments, for instance if metric was changed

The expected submission structure and required files:

 * `registration-results.csv` - cover file with experimental results
 * `computer-performances.json` - computer performance evaluation
 * landmarks in CSV files with relative path described
    in `registration-results.csv` in column 'Warped source landmarks'

The required files in the reference (ground truth):

 * `dataset.csv` - cover file with planed registrations
 * `computer-performances.json` - reference performance evaluation
 * `lnds_provided/` provided landmarks in CSV files with relative path described
    in `dataset.csv` in column 'Source landmarks'
 * `lnds_reference/` reference (ground truth) landmarks in CSV files with relative
    path described in `dataset_cover.csv` in both columns 'Target landmarks'
    and 'Source landmarks'

Sample usage::

    python evaluate_submission.py \
        -e ./results/BmUnwarpJ \
        -t ./data_images/pairs-imgs-lnds_histol.csv \
        -d ./data_images \
        -r ./data_images \
        -p ./bm_experiments/computer-performances_cmpgrid-71.json \
        -o ./output \
        --min_landmarks 0.20

DOCKER
------
Running in grad-challenge.org environment::

    python evaluate_submission.py \
        -e /input \
        -t /opt/evaluation/dataset.csv \
        -d /opt/evaluation/lnds_provided \
        -r /opt/evaluation/lnds_reference \
        -p /opt/evaluation/computer-performances.json \
        -o /output \
        --min_landmarks 0.20

or run locally::

    python bm_ANHIR/evaluate_submission.py \
        -e bm_ANHIR/submission \
        -t bm_ANHIR/dataset_ANHIR/dataset_medium.csv \
        -d bm_ANHIR/dataset_ANHIR/landmarks_user \
        -r bm_ANHIR/dataset_ANHIR/landmarks_all \
        -p bm_ANHIR/dataset_ANHIR/computer-performances_cmpgrid-71.json \
        -o output \
        --min_landmarks 0.20

References:

* https://grand-challengeorg.readthedocs.io/en/latest/evaluation.html

Copyright (C) 2018-2019 Jiri Borovec <jiri.borovec@fel.cvut.cz>
"""

import os
import sys
import re
import json
import time
import logging
import argparse
from functools import partial

import numpy as np
import pandas as pd

sys.path += [os.path.abspath('.'), os.path.abspath('..')]  # Add path to root
from birl.utilities.data_io import create_folder, load_landmarks, save_landmarks, update_path
from birl.utilities.dataset import common_landmarks, parse_path_scale
from birl.utilities.experiments import iterate_mproc_map, parse_arg_params, FORMAT_DATE_TIME, nb_workers
from birl.benchmark import ImRegBenchmark

NB_WORKERS = nb_workers(0.9)
NAME_CSV_RESULTS = 'registration-results.csv'
NAME_JSON_COMPUTER = 'computer-performances.json'
NAME_JSON_RESULTS = 'metrics.json'
COL_NORM_TIME = 'Norm. execution time [minutes]'
COL_FOUND_LNDS = 'Ration matched landmarks'
COL_TISSUE = 'Tissue kind'
CMP_THREADS = ('1', 'n')


def create_parser():
    """ parse the input parameters
    :return dict: parameters
    """
    # SEE: https://docs.python.org/3/library/argparse.html
    parser = argparse.ArgumentParser()
    parser.add_argument('-e', '--path_experiment', type=str, required=True,
                        help='path to the experiments', default='/input/')
    parser.add_argument('-t', '--path_table', type=str, required=True,
                        help='path to cover table (csv file)',
                        default='/opt/evaluation/dataset.csv')
    parser.add_argument('-d', '--path_dataset', type=str, required=True,
                        help='path to dataset with provided landmarks',
                        default='/opt/evaluation/provided')
    parser.add_argument('-r', '--path_reference', type=str, required=False,
                        help='path to complete ground truth landmarks')
    parser.add_argument('-p', '--path_comp_bm', type=str, required=False,
                        help='path to reference computer performance JSON')
    parser.add_argument('-o', '--path_output', type=str, required=True,
                        help='path to output results', default='/output/')
    # required number of submitted landmarks, match values in COL_FOUND_LNDS
    parser.add_argument('--min_landmarks', type=float, required=False, default=0.5,
                        help='ration of required landmarks in submission')
    parser.add_argument('--nb_workers', type=int, required=False, default=NB_WORKERS,
                        help='number of processes in parallel')
    parser.add_argument('--details', action='store_true', required=False,
                        default=False, help='export details for each case')
    return parser


def filter_landmarks(idx_row, path_output, path_dataset, path_reference):
    """ filter all relevant landmarks which were used and copy them to experiment

    :param tuple(idx,dict|Series) idx_row: experiment DataFrame
    :param str path_output: path to output folder
    :param str path_dataset: path to provided landmarks
    :param str path_reference: path to the complete landmark collection
    :return tuple(idx,float): record index and match ratio
    """
    idx, row = idx_row
    path_ref = update_path(row[ImRegBenchmark.COL_POINTS_MOVE], pre_path=path_reference)
    path_load = update_path(row[ImRegBenchmark.COL_POINTS_MOVE], pre_path=path_dataset)
    pairs = common_landmarks(load_landmarks(path_ref), load_landmarks(path_load),
                             threshold=1)
    if not pairs.size:
        return idx, 0.
    pairs = sorted(pairs.tolist(), key=lambda p: p[1])
    ind_ref = np.asarray(pairs)[:, 0]
    nb_common = min([len(load_landmarks(update_path(row[col], pre_path=path_reference)))
                     for col in [ImRegBenchmark.COL_POINTS_REF, ImRegBenchmark.COL_POINTS_MOVE]])
    ind_ref = ind_ref[ind_ref < nb_common]

    # moving and reference landmarks
    for col in [ImRegBenchmark.COL_POINTS_REF, ImRegBenchmark.COL_POINTS_MOVE]:
        path_in = update_path(row[col], pre_path=path_reference)
        path_out = update_path(row[col], pre_path=path_output)
        create_folder(os.path.dirname(path_out), ok_existing=True)
        save_landmarks(path_out, load_landmarks(path_in)[ind_ref])

    # save ratio of found landmarks
    len_lnds_ref = len(load_landmarks(update_path(row[ImRegBenchmark.COL_POINTS_REF],
                                                  pre_path=path_reference)))
    ratio_matches = len(pairs) / float(len_lnds_ref)
    return idx, ratio_matches


def normalize_exec_time(df_experiments, path_experiments, path_comp_bm=None):
    """ normalize execution times if reference and experiment computer is given

    :param DF df_experiments: experiment DataFrame
    :param str path_experiments: path to experiment folder
    :param str path_comp_bm: path to reference comp. benchmark
    """
    path_comp_bm_expt = os.path.join(path_experiments, NAME_JSON_COMPUTER)
    if ImRegBenchmark.COL_TIME not in df_experiments.columns:
        logging.warning('Missing %s among result columns.', ImRegBenchmark.COL_TIME)
        return
    if not path_comp_bm:
        logging.warning('Reference comp. perform. not specified.')
        return
    elif not all(os.path.isfile(p) for p in [path_comp_bm, path_comp_bm_expt]):
        logging.warning('Missing one of the JSON files: \n %s (%s)\n %s (%s)',
                        path_comp_bm, os.path.isfile(path_comp_bm),
                        path_comp_bm_expt, os.path.isfile(path_comp_bm_expt))
        return

    logging.info('Normalizing the Execution time.')
    with open(path_comp_bm, 'r') as fp:
        comp_ref = json.load(fp)
    with open(path_comp_bm_expt, 'r') as fp:
        comp_exp = json.load(fp)

    time_ref = np.mean([comp_ref['registration @%s-thread' % i] for i in CMP_THREADS])
    time_exp = np.mean([comp_exp['registration @%s-thread' % i] for i in CMP_THREADS])
    coef = time_ref / time_exp
    df_experiments[COL_NORM_TIME] = df_experiments[ImRegBenchmark.COL_TIME] * coef


def parse_landmarks(idx_row):
    """ parse the warped landmarks and reference and save them as cases

    :param tuple(int,series) idx_row: individual row
    :return {str: float|[]}: parsed registration pair
    """
    idx, row = idx_row
    row = dict(row)
    # lnds_ref = load_landmarks(update_path_(row[COL_POINTS_REF], path_experiments))
    # lnds_warp = load_landmarks(update_path_(row[COL_POINTS_MOVE_WARP], path_experiments))
    #     if isinstance(row[COL_POINTS_MOVE_WARP], str)else np.array([[]])
    path_dir = os.path.dirname(row[ImRegBenchmark.COL_POINTS_MOVE])
    match_lnds = np.nan_to_num(row[COL_FOUND_LNDS]) if COL_FOUND_LNDS in row else 0.
    item = {
        'name-tissue': os.path.basename(os.path.dirname(path_dir)),
        'scale-tissue': parse_path_scale(os.path.basename(path_dir)),
        'type-tissue': row.get(COL_TISSUE, None),
        'name-reference': os.path.splitext(os.path.basename(row[ImRegBenchmark.COL_POINTS_REF]))[0],
        'name-source': os.path.splitext(os.path.basename(row[ImRegBenchmark.COL_POINTS_MOVE]))[0],
        # 'reference landmarks': np.round(lnds_ref, 1).tolist(),
        # 'warped landmarks': np.round(lnds_warp, 1).tolist(),
        'matched-landmarks': match_lnds,
        'Robustness': row.get(ImRegBenchmark.COL_ROBUSTNESS, 0),
        'Norm-Time_minutes': row.get(COL_NORM_TIME, None),
        'Status': row.get(ImRegBenchmark.COL_STATUS, None),
    }
    # copy all columns with Affine statistic
    item.update({col.replace(' ', '-'): row[col] for col in row if 'affine' in col.lower()})
    # copy all columns with rTRE, TRE and Overlap
    # item.update({col.replace(' (final)', '').replace(' ', '-'): row[col]
    #              for col in row if '(final)' in col})
    item.update({col.replace(' (elastic)', '_elastic').replace(' ', '-'): row[col]
                 for col in row if 'TRE' in col})
    return idx, item


def compute_scores(df_experiments, min_landmarks=1.):
    """ compute all main metrics

    .. ref:: https://anhir.grand-challenge.org/Evaluation/

    :param DF df_experiments: complete experiments
    :param float min_landmarks: required number of submitted landmarks in range (0, 1),
        match values in COL_FOUND_LNDS
    :return dict: results
    """
    # if the initial overlap and submitted overlap do not mach, drop results
    if 'overlap points (final)' not in df_experiments.columns:
        raise ValueError('Missing `overlap points (final)` column,'
                         ' because there are probably missing wrap landmarks.')
    hold_overlap = df_experiments['overlap points (init)'] == df_experiments['overlap points (final)']
    mask_incomplete = ~hold_overlap | (df_experiments[COL_FOUND_LNDS] < min_landmarks)
    # rewrite incomplete cases by initial stat
    if sum(mask_incomplete) > 0:
        for col_f, col_i in zip(*_filter_tre_measure_columns(df_experiments)):
            df_experiments.loc[mask_incomplete, col_f] = df_experiments.loc[mask_incomplete, col_i]
        df_experiments.loc[mask_incomplete, ImRegBenchmark.COL_ROBUSTNESS] = 0.
        logging.warning('There are %i cases which incomplete landmarks.',
                        sum(mask_incomplete))

    df_expt_robust = df_experiments[df_experiments[ImRegBenchmark.COL_ROBUSTNESS] > 0.5]
    pd.set_option('expand_frame_repr', False)

    # pre-compute some optional metrics
    score_used_lnds = np.mean(df_expt_robust[COL_FOUND_LNDS]) \
        if COL_FOUND_LNDS in df_experiments.columns else 0
    # parse specific metrics
    scores = {
        'Average-Robustness': np.mean(df_experiments[ImRegBenchmark.COL_ROBUSTNESS]),
        'Average-Rank-Median-rTRE': np.nan,
        'Average-Rank-Max-rTRE': np.nan,
        'Average-used-landmarks': score_used_lnds,
    }
    # parse Mean & median specific measures
    for name, col in [('Median-rTRE', 'rTRE Median'),
                      ('Max-rTRE', 'rTRE Max'),
                      ('Average-rTRE', 'rTRE Mean'),
                      ('Norm-Time', COL_NORM_TIME)]:
        scores['Average-' + name] = np.mean(df_experiments[col])
        scores['Average-' + name + '-Robust'] = np.mean(df_expt_robust[col])
        scores['Median-' + name] = np.median(df_experiments[col])
        scores['Median-' + name + '-Robust'] = np.median(df_expt_robust[col])

    # filter all statuses in the experiments
    statuses = df_experiments[ImRegBenchmark.COL_STATUS].unique()
    # parse metrics according to TEST and TRAIN case
    for name, col in [('Average-rTRE', 'rTRE Mean'),
                      ('Median-rTRE', 'rTRE Median'),
                      ('Max-rTRE', 'rTRE Max'),
                      ('Robustness', 'Robustness')]:
        # iterate over common measures
        for stat_name, stat_func in [('Average', np.mean),
                                     ('Median', np.median)]:
            for status in statuses:
                df_expt_ = df_experiments[df_experiments[ImRegBenchmark.COL_STATUS] == status]
                scores[stat_name + '-' + name + '_' + status] = stat_func(df_expt_[col])
            # parse according to Tissue
            for tissue, df_tissue in df_experiments.groupby(COL_TISSUE):
                scores[stat_name + '-' + name + '_tissue_' + tissue] = stat_func(df_tissue[col])

    return scores


def _filter_tre_measure_columns(df_experiments):
    """ get columns related to TRE measures

    :param DF df_experiments: experiment table
    :return tuple(list(str),list(str)):
    """
    # copy the initial to final for missing
    cols_final = [col for col in df_experiments.columns if re.match(r'(r)?TRE', col)]
    cols_init = [col.replace('TRE', 'IRE') for col in cols_final]
    return cols_final, cols_init


def export_summary_json(df_experiments, path_experiments, path_output,
                        min_landmarks=1., details=True):
    """ summarize results in particular JSON format

    :param DF df_experiments: experiment DataFrame
    :param str path_experiments: path to experiment folder
    :param str path_output: path to generated results
    :param float min_landmarks: required number of submitted landmarks in range (0, 1),
        match values in COL_FOUND_LNDS
    :param bool details: exporting case details
    :return str: path to exported results
    """
    if COL_NORM_TIME not in df_experiments.columns:
        df_experiments[COL_NORM_TIME] = np.nan

    # note, we expect that the path starts with tissue and Unix sep "/" is used
    def _get_tissue(cell):
        tissue = cell.split(os.sep)[0]
        return tissue[:tissue.index('_')] if '_' in cell else tissue

    df_experiments[COL_TISSUE] = df_experiments[ImRegBenchmark.COL_POINTS_REF].apply(_get_tissue)

    # export partial results
    cases = list(iterate_mproc_map(parse_landmarks, df_experiments.iterrows(),
                                   desc='Parsing landmarks', nb_workers=1))

    # copy the initial to final for missing
    for col, col2 in zip(*_filter_tre_measure_columns(df_experiments)):
        mask = df_experiments[col].isnull()
        df_experiments.loc[mask, col] = df_experiments.loc[mask, col2]

    # parse final metrics
    scores = compute_scores(df_experiments, min_landmarks)

    path_comp_bm_expt = os.path.join(path_experiments, NAME_JSON_COMPUTER)
    if os.path.isfile(path_comp_bm_expt):
        with open(path_comp_bm_expt, 'r') as fp:
            comp_exp = json.load(fp)
    else:
        comp_exp = None

    results = {
        'aggregates': scores,
        'cases': dict(cases) if details else 'not exported',
        'computer': comp_exp,
        'submission-time': time.strftime(FORMAT_DATE_TIME, time.gmtime()),
        'required-landmarks': min_landmarks,
    }
    path_json = os.path.join(path_output, NAME_JSON_RESULTS)
    logging.info('exporting JSON results: %s', path_json)
    with open(path_json, 'w') as fp:
        json.dump(results, fp)
    return path_json


def replicate_missing_warped_landmarks(df_experiments, path_dataset, path_experiment):
    """ if some warped landmarks are missing replace the path by initial landmarks

    :param DF df_experiments: experiment table
    :param str path_dataset: path to dataset folder
    :param str path_experiment: path ti user experiment folder
    :return DF: experiment table
    """
    # find empty warped landmarks paths
    missing_mask = df_experiments[ImRegBenchmark.COL_POINTS_MOVE_WARP].isnull()
    # for the empty place the initial landmarks
    df_experiments.loc[missing_mask, ImRegBenchmark.COL_POINTS_MOVE_WARP] = \
        df_experiments.loc[missing_mask, ImRegBenchmark.COL_POINTS_MOVE]
    # for the empty place maximal execution time
    df_experiments.loc[missing_mask, ImRegBenchmark.COL_TIME] = \
        df_experiments[ImRegBenchmark.COL_TIME].max()

    count = 0
    # iterate over whole table
    for idx, row in df_experiments.iterrows():
        path_csv = update_path(row[ImRegBenchmark.COL_POINTS_MOVE_WARP], pre_path=path_experiment)
        if not os.path.isfile(path_csv):
            path_csv = update_path(row[ImRegBenchmark.COL_POINTS_MOVE], pre_path=path_dataset)
            df_experiments.loc[idx, ImRegBenchmark.COL_POINTS_MOVE_WARP] = path_csv
            count += 1

    logging.info('Missing warped landmarks: %i', count)
    return df_experiments


def main(path_experiment, path_table, path_dataset, path_output, path_reference=None,
         path_comp_bm=None, nb_workers=NB_WORKERS, min_landmarks=1., details=True):
    """ main entry point

    :param str path_experiment: path to experiment folder
    :param str path_table: path to assignment file (requested registration pairs)
    :param str path_dataset: path to provided landmarks
    :param str path_output: path to generated results
    :param str|None path_reference: path to the complete landmark collection,
        if None use dataset folder
    :param str|None path_comp_bm: path to reference comp. benchmark
    :param int nb_workers: number of parallel processes
    :param float min_landmarks: required number of submitted landmarks in range (0, 1),
        match values in COL_FOUND_LNDS
    :param bool details: exporting case details
    """

    path_results = os.path.join(path_experiment, ImRegBenchmark.NAME_CSV_REGISTRATION_PAIRS)
    if not os.path.isfile(path_results):
        raise AttributeError('Missing experiments results: %s' % path_results)
    path_reference = path_dataset if not path_reference else path_reference

    # drop time column from Cover which should be empty
    df_overview = pd.read_csv(path_table).drop([ImRegBenchmark.COL_TIME], axis=1, errors='ignore')
    # drop Warp* column from Cover which should be empty
    df_overview = df_overview.drop([col for col in df_overview.columns if 'warped' in col.lower()],
                                   axis=1, errors='ignore')
    df_results = pd.read_csv(path_results)
    df_results = df_results[[col for col in list(ImRegBenchmark.COVER_COLUMNS_WRAP) + [ImRegBenchmark.COL_TIME]
                             if col in df_results.columns]]
    df_experiments = pd.merge(df_overview, df_results, how='left', on=ImRegBenchmark.COVER_COLUMNS)
    df_experiments.drop([ImRegBenchmark.COL_IMAGE_REF_WARP, ImRegBenchmark.COL_POINTS_REF_WARP],
                        axis=1, errors='ignore', inplace=True)

    df_experiments = replicate_missing_warped_landmarks(df_experiments, path_dataset, path_experiment)

    normalize_exec_time(df_experiments, path_experiment, path_comp_bm)

    logging.info('Filter used landmarks.')
    _filter_lnds = partial(filter_landmarks, path_output=path_output,
                           path_dataset=path_dataset, path_reference=path_reference)
    for idx, ratio in iterate_mproc_map(_filter_lnds, df_experiments.iterrows(),
                                        desc='Filtering', nb_workers=nb_workers):
        df_experiments.loc[idx, COL_FOUND_LNDS] = np.round(ratio, 2)

    logging.info('Compute landmarks statistic.')
    _compute_lnds_stat = partial(ImRegBenchmark.compute_registration_statistic,
                                 df_experiments=df_experiments,
                                 path_dataset=path_output,
                                 path_experiment=path_experiment)
    # NOTE: this has to run in SINGLE thread so there is SINGLE table instance
    list(iterate_mproc_map(_compute_lnds_stat, df_experiments.iterrows(),
                           desc='Statistic', nb_workers=1))

    path_results = os.path.join(path_output, os.path.basename(path_results))
    logging.debug('exporting CSV results: %s', path_results)
    df_experiments.to_csv(path_results)

    path_json = export_summary_json(df_experiments, path_experiment, path_output,
                                    min_landmarks, details)
    return path_json


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    arg_params = parse_arg_params(create_parser())
    logging.info('running...')
    main(**arg_params)
    logging.info('DONE')
