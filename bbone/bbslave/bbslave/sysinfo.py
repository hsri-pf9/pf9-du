# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'leb'
import platform
import netifaces
import os

def get_sysinfo():
    """
    Returns a dictionary describing the host and operating system.
    :rtype: dict
    """

    return {
        'hostname': platform.node(),
        'os_info': ' '.join(platform.dist()),
        'arch': platform.machine(),
        'os_family': platform.system()
    }

def get_host_id():
    """
    Attempts to compute a unique host id.

    Currently uses the MAC address of the first network interface
    alphabetically sorted by interface name.
    If this fails, defaults to the supplied hostname.
    For more information about the netifaces library, see:
    http://alastairs-place.net/projects/netifaces/
    The host id can be overridden for test purposes using
    the HOSTAGENT_HOST_ID environment variable.

    :param str hostname: current machine's host name
    :rtype: str
    """

    if 'HOSTAGENT_HOST_ID' in os.environ:
        return os.environ['HOSTAGENT_HOST_ID']

    hostname = platform.node()
    ifaces = sorted(netifaces.interfaces())
    for iface in ifaces:
        addresses = netifaces.ifaddresses(iface)
        try:
            mac = addresses[netifaces.AF_LINK][0]['addr']
        except (IndexError, KeyError):
            continue
        # Avoid the loopback MAC address
        if mac == '00:00:00:00:00:00':
            continue
        return mac

    # TODO: Don't use hostname. Check for a persistent host uuid file,
    # and if not present, generate uuid and store in that file.
    return hostname
