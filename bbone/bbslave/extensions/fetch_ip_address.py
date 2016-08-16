#!/opt/pf9/hostagent/bin/python

# Copyright 2015 Platform9 Systems Inc.
# All Rights Reserved.


import json
import netifaces
import re
import sys


def get_addresses():
    """
    Get non local IPv4 addresses
    """
    nw_ifs = netifaces.interfaces()
    nonlocal_ips = set()
    ignore_ip_re = re.compile('^(0.0.0.0|127.0.0.1)$')
    ignore_if_re = re.compile('^(q.*-[0-9a-fA-F]{2}|tap.*)$')

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
                        nonlocal_ips.add(ip['addr'])
            else:
                # move to next interface if this interface doesn't
                # have IPv4 addresses
                continue
        except KeyError:
            pass

    return list(nonlocal_ips)


if __name__ == '__main__':
    out = get_addresses()
    sys.stdout.write(json.dumps(out))
