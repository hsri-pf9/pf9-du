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
    # name of the volumes. Return it as a list.
    out = commands.getoutput("sudo /sbin/vgs | tail -n+2 | awk '{print $1}'")
    volumes_list = out.split()
    return volumes_list

if __name__ == '__main__':
    out = get_volumes_list()
    sys.stdout.write(json.dumps(out))
