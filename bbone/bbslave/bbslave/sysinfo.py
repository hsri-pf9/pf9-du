# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'leb'
import platform
import ConfigParser
import uuid
import os
import socket

def get_sysinfo():
    """
    Returns a dictionary describing the host and operating system.
    :rtype: dict
    """

    return {
        'hostname': socket.getfqdn(),
        'os_info': ' '.join(platform.dist()),
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
    cfg = ConfigParser.ConfigParser()
    cfg.read([host_id_file])
    if cfg.has_section(SECT_NAME) and cfg.has_option(SECT_NAME, OPT_NAME):
        host_id = cfg.get(SECT_NAME, OPT_NAME)
    else:
        host_id = str(uuid.uuid4())
        cfg = ConfigParser.ConfigParser()
        cfg.add_section(SECT_NAME)
        cfg.set(SECT_NAME, OPT_NAME, host_id)
        with open(host_id_file, 'w') as fp:
            cfg.write(fp)
    return host_id
