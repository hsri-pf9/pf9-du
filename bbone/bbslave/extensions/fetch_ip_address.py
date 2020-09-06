#!/opt/pf9/hostagent/bin/python

# Copyright 2015 Platform9 Systems Inc.
# All Rights Reserved.


import json
import netifaces
import re
import sys
import ipaddress

def get_addresses():
    """
    Get non local IPv4 addresses
    """
    nw_ifs = netifaces.interfaces()
    nonlocal_ips = set()
    ignore_if_re = re.compile('^(q.*-[0-9a-fA-F]{2}|tap.*|kube-ipvs.*)$')

    for iface in nw_ifs:
        if ignore_if_re.match(iface):
            continue
        addrs = netifaces.ifaddresses(iface)

        ips = []
        if netifaces.AF_INET in addrs:
            ips.extend(addrs[netifaces.AF_INET])
        if netifaces.AF_INET6 in addrs:
            ips.extend(addrs[netifaces.AF_INET6])

        for ip in ips:
            try:
                ip_addr = ipaddress.ip_address(ip['addr'])
            except ValueError:
                # the link local sometime appears to have an invalid prefix
                # ignore those interfaces
                continue
            # Add non-link local/loopback or multicast ip addresses
            if not (ip_addr.is_loopback or ip_addr.is_link_local or ip_addr.is_multicast):
                nonlocal_ips.add(ip['addr'])

    return list(nonlocal_ips)


if __name__ == '__main__':
    out = get_addresses()
    sys.stdout.write(json.dumps(out))
