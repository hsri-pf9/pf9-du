# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

"""
Module that builds a bundle of all support information from a host
"""

__author__ = 'Platform 9'

import glob
import logging
import os
import tarfile

from subprocess import CalledProcessError, check_call

"""
Want to be able to do the following eventually:
1. Allow apps to provide their own manifest in a directory and this gatherer
captures it at run time for the app.
2. Run a command on the host and capture its output in a file in the bundle.
"""

file_list = [
    '/etc/pf9/*',
    '/var/log/pf9/*',
    '/var/opt/pf9/hostagent/*',
    '/var/opt/pf9/hypervisor_details',
]

support_logging_dir = '/var/log/pf9/support'
support_script = '/opt/pf9/hostagent/bin/run_support_scripts.sh'

def generate_support_bundle(out_tgz_file, logger=logging):
    """
    Run the support scripts and generate a tgz file in
    /var/opt/pf9/hostagent. Overwrites the previously generated
    tgz file if it exists.
    """
    logger.info('Writing out support file %s', out_tgz_file)
    try:
        if not os.path.isdir(support_logging_dir):
            os.makedirs(support_logging_dir)

        support_logfile = os.path.join(support_logging_dir, 'support.txt')
        with open(support_logfile, 'w') as f:
            check_call([support_script, support_logging_dir], stdout=f, stderr=f)
    except:
        logger.exception("Failed to run the support scripts.")

    tgzfile = tarfile.open(out_tgz_file, 'w:gz')
    for pattern in file_list:
        expanded_pattern = os.path.expandvars(os.path.expanduser(pattern))
        for file in glob.iglob(expanded_pattern):
            try:
                tgzfile.add(file)
            except OSError as e:
                logger.warn(e)
    tgzfile.close()

if __name__ == '__main__':
    tmp_file = '/tmp/pf9-support.tgz'
    generate_support_bundle(tmp_file)
