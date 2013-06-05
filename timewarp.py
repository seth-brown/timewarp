#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
Author: Seth Brown
Description: Time Machine Reservoir Sampler
Date: 27 Jan 2013
Dependencies: Python 2.6x+
"""

import os
import sys
from math import log
from collections import namedtuple
from random import random
import heapq
import datetime
from subprocess import Popen, PIPE
import logging
import json


def df(path):
    """ Return the free disk space (in Mb) at the specified path
    """
    st = os.statvfs(path)
    free = (st.f_bavail * st.f_frsize) / 1024 / 1024

    return free


def gen_wts(bups):
    """ Assemble file names, time stamps, and associated weights
        for each Time Machine backup image.

        Parameters
        ------------------
        bups: iterable of backup file names

        Output
        --------------
        datum, weight: namedtuple of TM file name and associated weight
    """
    _temp = namedtuple('data', 'file_name, weight')
    today = datetime.datetime.today().replace(microsecond=0)
    # weight function
    weight = lambda dt, dg: 1 + 1e2*1.618**(-dt) + 1e2*log(dg)
    # convert TM file names into readible time stamps
    bups = sorted([(int(bup.replace('-', '')), bup) for bup in bups],
                  key=lambda t: t[0])
    latest_bup = bups[-1]
    nbups = bups[1:]
    data = []
    for bup, nbup  in zip(bups, nbups):
        # calculte the time in days between today and the backup
        ts = datetime.datetime.strptime(str(bup[0]), "%Y%m%d%H%M%S")
        t_delta = (today - ts).days

        # calculte the time in days between the backup and the next backup
        nts = datetime.datetime.strptime(str(nbup[0]), "%Y%m%d%H%M%S")
        nt_delta_t = (today - nts).days

        g_delta = float(t_delta - nt_delta_t) / 7
        # when the gap is < 1w, set to 1
        if g_delta < 1:
            g_delta = 1
        wt = weight(t_delta, g_delta)
        data.append(_temp(bup[1], wt))

    return [datum for datum in data] + [_temp(latest_bup[1], 1e4)]


def aes(strm, k=1):
    """ Weighted reservoir sampling without replacement implementation.

        See [Efraimidis et. al][1].

        k = reservoir size
        rsv = reservoir
        strm = stream
        wts = associated weights for the stream

        [1]: http://arxiv.org/pdf/1012.0256.pdf
    """
    rsv = []
    heapq.heapify(rsv)
    # generate a key and fill the reservoir to k elements with associated keys
    for n, (el, wi) in enumerate(strm):
        ki = random()**(1. / wi)
        if n < k:
            heapq.heappush(rsv, (ki, el))

        # if the reservoir is full, find a minimum threshold, t.
        # if ki is large then t, pop t and push ki onto the heap.
        else:
            if len(rsv) > 1:
                t, _ = heapq.nsmallest(1, rsv)[0]
                if ki > t:
                    heapq.heapreplace(rsv, (ki, el))

    # yield k elements with the largest keys, this is the reservoir sample.
    for elem in heapq.nlargest(k, rsv):

        yield elem[1]


def wrapper(*args):
    """ CLI wrapper for external commands
    """
    opts = [i for i in args]
    cmd = [] + opts
    process = Popen(cmd, stdout=PIPE)
    process.communicate()[0]

    return process


def del_bups(del_bups, base_path):
    """ Delete a list of TM backup files
    """
    files = [os.path.join(base_path, _) for _ in del_bups]
    for f in files:
        wrapper('/usr/bin/sudo', '/usr/bin/tmutil', 'delete', f)


def get_bups(tm_backup):
    bups = [name for name in os.listdir(tm_backup)
            if not name.startswith(('.', 'Latest'))]
    bups = filter(lambda _: _.endswith('inProgress') is False, bups)

    return bups


def timewarp(tm_backup, bups, threshold, mode):
    """ Run Time Warp

        tm_backup: string, path to TM backup
        bups: list, potential backups to delete
        threshold: int (in MB) the amount of free space at which Time Warp
                        is activated; Time Warp runs when fs < threshold
        mode: string, if 'live' backups are deleted, else dry-run

        If the available free space is < threshold, run A-ES/remove backups
    """
    # remove one Time Machine image in each iteration
    res_size = len(bups) - 1
    # these backups are in the reservoir
    res_data = gen_wts(bups)
    res_bups = set(aes(res_data, k=res_size))
    # these are the backups to delete
    todel_bups = [bup for bup in bups if bup not in res_bups]
    if mode == 'live':
        del_bups(todel_bups, tm_backup)
    else:
        bup_name = todel_bups[0]
        return bup_name


def logger(log_file):
    """ Log deleted Time Machine backups. Spawn a log
        object with 2 tab delimited fields per line:

        time stamp: the time a give backup was deleted
        file: the path of the deleted backup

        Parameters:
        -------------------
        log_file: string, /Users/drbunsen/Desktop/warp.log
    """
    l = logging.getLogger("warp_log")
    l.setLevel(logging.INFO)
    f = logging.FileHandler(log_file)
    l.addHandler(f)
    fmttr = logging.Formatter('%(asctime)s\t%(message)s', "%Y-%m-%d %H:%M:%S")
    f.setFormatter(fmttr)

    return l


def validate_config(**kwargs):
    """ Verify that the config is property setup
    """
    try:
        volume = kwargs['volume']
        tm_path = os.path.exists(volume)
        if tm_path is True:
            mode = kwargs['mode']
            threshold = kwargs['threshold']
            l = kwargs.get('log', False)
            if l is not False:
                l = logger(l)
        return volume, mode, threshold, l
    except:
        print "\nThe config file is mis-configured.\n"
    sys.exit(0)


def handler(**kwargs):
    """ Manage Time Warp config options and control flow.
    """
    volume, mode, threshold, l = validate_config(**kwargs)
    n_bups = len(get_bups(volume))
    free = df(volume)
    # dry-run: nothing is deleted in this mode
    if mode != 'live':
        print '\nTime Warp is running in **SAFE MODE**'
        print '=====================================\n'
        print 'The following backups would have been deleted:\n'
        bups = get_bups(volume)
        ave_size = float(free) / len(bups)
        while free < threshold and len(bups) > 0:
            bup_name = timewarp(volume, bups, threshold, mode)
            bups.remove(bup_name)
            free += ave_size
            print bup_name
            bup_name = os.path.join(volume, bup_name)
            if l is not False:
                l.info(bup_name)
    else:
        while free < threshold and len(get_bups(volume)) > 0:
            bups = get_bups(volume)
            bup_name = timewarp(volume, bups, threshold, mode)
            free = df(volume)


def main(config_file):
    config = json.load(open(config_file))
    handler(**config)

if __name__ == '__main__':
    main(sys.argv[1])
