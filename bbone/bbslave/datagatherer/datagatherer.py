# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

"""
Module that builds a bundle of all support information from a host
"""

__author__ = 'Platform 9'

import glob
import os
import tarfile

"""
Want to be able to do the following eventually:
1. Allow apps to provide their own manifest in a directory and this gatherer
captures it at run time for the app.
2. Run a command on the host and capture its output in a file in the bundle.
"""

# TODO: For now, hardcoded list of files of interest. Should maintain
# this list out of the hostagent scope

file_list = [
    # TODO Log files are now stored in /var/log/pf9/.
    # Remove the next line when /var/log/pf9-* files no longer exist.
    '/var/log/pf9*',
    '/var/log/pf9/*'
]


def generate_support_bundle(out_tgz_file, logger):
    # Clear out any previous file
    # Generate tgz file in /var/opt/pf9/hostagent

    # Opening the file in 'w' mode, which will overwrite the previous file
    logger.info('Writing out support file %s', out_tgz_file)
    tgzfile = tarfile.open(out_tgz_file, 'w:gz')
    for pattern in file_list:
        expanded_pattern = os.path.expandvars(
                os.path.expanduser(pattern))
        for file in glob.iglob(expanded_pattern):
                tgzfile.add(file)
    tgzfile.close()

if __name__ == '__main__':
    tmp_file = '/tmp/pf9-support.tgz'
    generate_support_bundle(tmp_file)
