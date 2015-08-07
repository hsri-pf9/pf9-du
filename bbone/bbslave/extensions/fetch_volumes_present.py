#!/opt/pf9/hostagent/bin/python

# Copyright 2015 Platform9 Systems Inc.
# All Rights Reserved.

import commands
import json
import sys
import os.path

def get_volumes_list():
    """
    Return the list of volumes present on the host
    """
    # Check if vgs utility is present. If not present, we cannot run vgs
    # to find list of volumes. We need lvm2 package to run these commands.
    if os.path.isfile("/sbin/vgs") is False:
        return ["Error: No vgs command found."]
    # tail -n+2 removes the header line followed by awk to get only the
    # name of the volumes, size of volume and free space. Return it as a
    # list of dictionaries.
    out = commands.getoutput("sudo /sbin/vgs | tail -n+2 | awk '{print $1, $6, $7}'")
    volumes_list = out.splitlines(False)
    res = []
    for volume in volumes_list:
        volume_data = volume.split()
        res.append(dict(name=volume_data[0],
                        size=volume_data[1],
                        free=volume_data[2]))
    return res

if __name__ == '__main__':
    out = get_volumes_list()
    sys.stdout.write(json.dumps(out))
