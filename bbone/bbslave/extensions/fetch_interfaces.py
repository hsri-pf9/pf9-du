#!/opt/pf9/hostagent/bin/python

# Copyright 2016 Platform9 Systems Inc.
# All Rights Reserved.


import json
import netifaces
import sys
import re
import subprocess
import os


def get_addresses_and_names():
    """
    Get interfaces and their IPv4 addresses
    """
    nw_ifs = netifaces.interfaces()
    interface_ips = {}

    ignore_ip_re = re.compile('^(0.0.0.0|127.0.0.1)$')
    ignore_if_re = re.compile('^(q.*-[0-9a-fA-F]{2}|tap.*)$')

    # Get list of ovs-bridges if present.
    ovs_list = []
    try:
        if os.path.isfile("/usr/bin/ovs-vsctl"):
            process = subprocess.Popen(["sudo", "ovs-vsctl", "list-br"],
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
            out, err = process.communicate()
            if not process.returncode:
                ovs_list = out.split()
    except:
        pass
    for iface in nw_ifs:
        if ignore_if_re.match(iface):
            continue
        addrs = netifaces.ifaddresses(iface)
        try:
            if netifaces.AF_INET in addrs:
                ips = addrs[netifaces.AF_INET]
                for ip in ips:
                    # Not interested in loopback IPs
                    if not ignore_ip_re.match(ip['addr']):
                        interface_ips[iface] = ip['addr']
            else:
                # move to next interface if this interface doesn't
                # have IPv4 addresses
                pass
        except KeyError:
            pass

    return {'iface_ip': interface_ips, 'ovs_bridges': ovs_list}

if __name__ == '__main__':
    out = get_addresses_and_names()
    sys.stdout.write(json.dumps(out))
