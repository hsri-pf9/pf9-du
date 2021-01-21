# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'leb'
import platform
from six.moves.configparser import ConfigParser
import uuid
import os
import re
import socket
import subprocess
import cpuinfo
import psutil
import sys

_dist_res = (re.compile("(?:DISTRIB_ID\s*=)\s*(.*)", re.I),
             re.compile("(?:DISTRIB_RELEASE\s*=)\s*(.*)", re.I),
             re.compile("(?:DISTRIB_CODENAME\s*=)\s*(.*)", re.I))

CPU_INFO = None

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

def get_sysinfo(log):
    """
    Returns a dictionary describing the host and operating system.
    :rtype: dict
    """
    return {
        'hostname': socket.getfqdn(),
        'os_info': _get_os_info(),
        'arch': platform.machine(),
        'os_family': platform.system(),
        'cpu_info': get_cpu_info(log)
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

def get_cpu_info(log):
    """
    Returns a dictionary describing cpu info.
    :rtype: dict
    """
    global CPU_INFO

    if CPU_INFO:
        return CPU_INFO

    log.debug("Fetching CPU_INFO as it is not cached")

    cpu_sockets = 0
    try:
        cpu_sockets = int(subprocess.check_output('grep "physical id" /proc/cpuinfo | sort -u | wc -l', shell=True))
    except Exception:
        log.exception('Could not parse out socket information from /proc/cpuinfo, defaulting to 0')

    cpu_cores = psutil.cpu_count(logical=False)
    cpu_total_threads = psutil.cpu_count()
    cpu_threads_per_core = cpu_total_threads / cpu_cores
    cpu_threads = {'total': cpu_total_threads, 'per_core': cpu_threads_per_core}
    cpu_info = cpuinfo.get_cpu_info()
    cpu_raw_capacity = float(cpu_info['hz_actual_friendly'][:-4])
    if cpu_sockets:
        capacity_per_socket = str(cpu_raw_capacity/cpu_sockets) + ' Ghz'
    else:
        capacity_per_socket = 'N/A'
    cpu_capacity = {
            'total': cpu_info['hz_actual_friendly'],
            'per_socket': capacity_per_socket,
            'per_core': str(cpu_raw_capacity/cpu_cores) + ' Ghz',
            'per_thread': str(cpu_raw_capacity/cpu_total_threads) + ' Ghz'
            }
    cpu_arch = cpu_info['arch']
    cpu_vendor = cpu_info['vendor_id_raw']
    cpu_model = {'model_id': cpu_info['model'], 'model_name': cpu_info['brand_raw']}
    cpu_features = cpu_info['flags']

    virtual_or_physical = 'unknown'
    try:
        virtual_check = subprocess.run('grep hypervisor /proc/cpuinfo', shell=True, stdout=subprocess.DEVNULL)
        virtual_or_physical = 'physical'
        if not virtual_check.returncode:
            virtual_or_physical = 'virtual'
    except Exception:
        log.exception('Could not parse out virtual/physical info from /proc/cpuinfo, defaulting to "unknown"')

    try:
        vmware_tools_check = subprocess.run('command -v vmware-toolbox-cmd', shell=True, stdout=subprocess.DEVNULL)
        if not vmware_tools_check.returncode:
            virtual_or_physical += ' (VMware)'
    except Exception:
        log.exception('Could not determine VMware Tools precense, defaulting to absent')

    CPU_INFO = {
        'cpu_sockets': cpu_sockets,
        'cpu_cores': cpu_cores,
        'cpu_threads': cpu_threads,
        'cpu_capacity': cpu_capacity,
        'cpu_arch': cpu_arch,
        'cpu_vendor': cpu_vendor,
        'cpu_model': cpu_model,
        'cpu_features': cpu_features,
        'virtual/physical': virtual_or_physical
    }

    return CPU_INFO
