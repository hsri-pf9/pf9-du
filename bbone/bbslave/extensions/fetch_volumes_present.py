#!/opt/pf9/hostagent/bin/python

# Copyright 2015 Platform9 Systems Inc.
# All Rights Reserved.

import commands
import json
import sys

def get_volumes_list():
    """
    Return the list of volumes present on the host
    """
    # tail -n+2 removes the header line followed by awk to get only the
    # name of the volumes. Return it as a list.
    out = commands.getoutput("sudo vgs | tail -n+2 | awk '{print $1}'")
    if "command not found" in out:
        return []
    volumes_list = out.split()
    return volumes_list

if __name__ == '__main__':
    out = get_volumes_list()
    sys.stdout.write(json.dumps(out))
