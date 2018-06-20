#!/opt/pf9/hostagent/bin/python

# Copyright 2015 Platform9 Systems Inc.
# All Rights Reserved.

import json
import sys
import subprocess
import os.path

def get_volumes_list():
    """
    Return the list of volumes present on the host
    """
    # Check if vgs utility is present. If not present, we cannot run vgs
    # to find list of volumes. We need lvm2 package to run these commands.
    if os.path.isfile("/sbin/vgs") is False:
        return ["Error: No vgs command found."]
    # check_output provides multi-line string output. volume_data is a list of
    # lists which is used to get only the name of the volumes, size of volume
    # and free space. Return it as a list of dictionaries.
    volume_data = []
    required_data = []
    out = subprocess.check_output(["sudo", "/sbin/vgs"])
    for volume in out.splitlines():
        volume_data.append(volume.split())
    # To ignore any errors in output of `sudo /sbin/vgs`, checking for VG in
    # output line as we get required data in next line. Result will be added
    # in required_data once VG is found in line
    process_lines = False
    for line in volume_data:
        if process_lines:
            required_data.append(dict(name=line[0], size=line[5],
                                      free=line[6]))
        if line[0] == "VG":
            process_lines = True
    return required_data

if __name__ == '__main__':
    out = get_volumes_list()
    sys.stdout.write(json.dumps(out))
