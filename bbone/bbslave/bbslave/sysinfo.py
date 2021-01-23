# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'leb'
import platform
from six.moves.configparser import ConfigParser
import uuid
import os
import re
import socket

_dist_res = (re.compile("(?:DISTRIB_ID\s*=)\s*(.*)", re.I),
             re.compile("(?:DISTRIB_RELEASE\s*=)\s*(.*)", re.I),
             re.compile("(?:DISTRIB_CODENAME\s*=)\s*(.*)", re.I))

def _get_os_info():
    """
    The Python platform module detects Ubuntu distributions as Debian,
    so check the lsb release file first. See IAAS-3596.
    """
    try:
        with open("/etc/lsb-release", "rU") as f:
            lsb_contents = f.read()
        dist = [dist_re.search(lsb_contents).group(1).strip()
                for dist_re in _dist_res
                if dist_re.search(lsb_contents)]
    except:
        dist = []
    if len(dist) != 3:
        dist = platform.dist()
    return ' '.join(dist)

def get_sysinfo():
    """
    Returns a dictionary describing the host and operating system.
    :rtype: dict
    """
    return {
        'hostname': socket.getfqdn(),
        'os_info': _get_os_info(),
        'arch': platform.machine(),
        'os_family': platform.system()
    }


def get_host_id(base_dir='/etc/pf9'):
    """
    Returns a unique identifier for the host.
    Can be overridden with HOSTAGENT_HOST_ID environment variable.
    :rtype: str
    """

    if 'HOSTAGENT_HOST_ID' in os.environ:
        return os.environ['HOSTAGENT_HOST_ID']

    if 'HOSTAGENT_HOST_ID_BASEDIR' in os.environ:
        base_dir = os.environ['HOSTAGENT_HOST_ID_BASEDIR']

    host_id_file = os.path.join(base_dir, 'host_id.conf')
    SECT_NAME = 'hostagent'
    OPT_NAME = 'host_id'
    cfg = ConfigParser()
    cfg.read([host_id_file])
    if cfg.has_section(SECT_NAME) and cfg.has_option(SECT_NAME, OPT_NAME):
        host_id = cfg.get(SECT_NAME, OPT_NAME)
    else:
        host_id = str(uuid.uuid4())
        cfg = ConfigParser()
        cfg.add_section(SECT_NAME)
        cfg.set(SECT_NAME, OPT_NAME, host_id)
        with open(host_id_file, 'w') as fp:
            cfg.write(fp)
    return host_id
