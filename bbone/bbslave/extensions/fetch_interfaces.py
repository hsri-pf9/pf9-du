#!/opt/pf9/hostagent/bin/python

# Copyright 2016 Platform9 Systems Inc.
# All Rights Reserved.


import json
import netifaces
import sys
import re
import subprocess
import os
import ipaddress

def get_addresses_and_names():
    """
    Get interfaces and their IPv4 addresses
    """
    nw_ifs = netifaces.interfaces()
    interface_ips = {}
    interface_info = {}

    ignore_if_re = re.compile('^(q.*-[0-9a-fA-F]{2}|tap.*|kube-ipvs.*)$')

    # Get list of ovs-bridges if present.
    ovs_list = []
    try:
        if os.path.isfile("/usr/bin/ovs-vsctl"):
            process = subprocess.Popen(["sudo", "ovs-vsctl", "list-br"],
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
            out, err = process.communicate()
            if not process.returncode:
                ovs_list = out.decode().split()
    except:
        pass

    for iface in nw_ifs:
        if ignore_if_re.match(iface):
            continue
        addrs = netifaces.ifaddresses(iface)

        ips = []
        if netifaces.AF_INET in addrs:
            ips.extend(addrs[netifaces.AF_INET])
        if netifaces.AF_INET6 in addrs:
            ips.extend(addrs[netifaces.AF_INET6])
        if netifaces.AF_LINK in addrs:
            mac_addr = addrs[netifaces.AF_LINK][0]['addr']

        for ip in ips:
            try:
                ip_addr = ipaddress.ip_address(ip['addr'])
            except ValueError:
                # the link local sometime appears to have an invalid prefix
                # ignore those interfaces
                continue

            # Add non-link local/loopback or multicast ip addresses
            if not (ip_addr.is_loopback or ip_addr.is_link_local or ip_addr.is_multicast):
                interface_ips[iface] = ip['addr']
                interface_info[iface] = {'mac': mac_addr, 'ifaces': ips}

    return {'iface_ip': interface_ips, 'ovs_bridges': ovs_list, 'iface_info': interface_info}

if __name__ == '__main__':
    out = get_addresses_and_names()
    sys.stdout.write(json.dumps(out))
