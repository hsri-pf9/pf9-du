# Copyright 2015 Platform9 Systems Inc.
# All Rights Reserved.

from glob import glob
from bbcommon.exceptions import Pf9CommsConfigurationError
import subprocess
from os import path, environ

def get_comms_cfg(log, basedir, baseurl):
    """
    Returns the backbone application configuration for pf9-comms based
    on the RPM located in the specified base directory. It is assumed that
    the Debian version of the package has the same version string.
    """
    if 'PF9_COMMS_FILENAME' in environ and 'PF9_COMMS_VERSION' in environ:
        # For testing purposes
        version = environ['PF9_COMMS_VERSION']
        pkg_filename = environ['PF9_COMMS_FILENAME']
    else:
        expr = '%s/pf9-comms*.rpm' % basedir
        pkgs = glob(expr)
        if len(pkgs) != 1:
            log.error('Number of pf9-comms RPMs found: %s', len(pkgs))
            raise Pf9CommsConfigurationError
        args = ['/bin/rpm', '-qp', '--qf', '%{VERSION}-%{RELEASE}', pkgs[0]]
        cmd = subprocess.Popen(args, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        version, stderr = cmd.communicate()
        if cmd.returncode != 0:
            log.error('query of pf9-comms RPM failed: %s' % stderr)
            raise Pf9CommsConfigurationError
        pkg_filename = path.basename(pkgs[0])
    return {
        'version': version,
        'running': True,
        'config': {},
        'url': '%s/%s' % (baseurl, pkg_filename)
    }


def insert_comms(desired_apps, comms_cfg):
    """
    Inserts the specified pf9-comms configuration into the supplied dictionary.
    """
    if type(desired_apps) is dict:
        desired_apps['pf9-comms'] = comms_cfg
    return desired_apps


def remove_comms(hosts):
    """
    Removes pf9-comms configuration from the 'apps' and 'desired_apps' section
    of every host configuration in the supplied list.
    """
    for host in hosts:
        for key in ('apps', 'desired_apps'):
            if key in host:
                host[key].pop('pf9-comms', None)
    return hosts