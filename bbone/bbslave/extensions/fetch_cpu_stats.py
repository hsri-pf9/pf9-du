#!/opt/pf9/hostagent/bin/python

# Copyright 2016 Platform9 Systems Inc.
# All Rights Reserved.

import json
import sys
import subprocess
import os

def load_process_list():
    """
    Extension mechanism for users adding other processes to monitor
    To monitor a new process, add a zero sized file with the filename
    as same as the process name you would like to monitor under
    /etc/pf9/cpustats_procnames/ directory
    Return:
         Python list of process names that needs to be monitored
    """
    process_list = []
    try:
        process_list = os.listdir('/etc/pf9/cpustats_procnames')
    except OSError:
        # Looks like we can't either see the directory or we don't
        # have permissions
        pass
    return process_list

def get_process_cpu_utilization(process_list):
    """
    Get cpu utilization for processes using top
    If a particular process isn't present in the system or if there
    is an error in executing a command, this method return 0.0 as cpu
    utilization for that process.
    Input:
        process_list - List of process names for which cpu% usage is required
    Returns:
        result - Python Dict with process & cpu % usage snapshot
                 {} empty dict if pgrep or top is not installed
    """
    result = {}
    if os.path.isfile('/usr/bin/pgrep') and os.path.isfile('/usr/bin/top'):
        for process in process_list:
            cpu_percent = "0.0"
            cmd1 = subprocess.Popen(["pgrep",process], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
            out, err = cmd1.communicate()
            if cmd1.returncode == 0:
                # We only grab the cpu percent of the first process if there
                # are more than 1 process with the same name.
                pid = out.split()[0]
                cmd2 = subprocess.Popen(["top","-b","-n1","-p",pid],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, err = cmd2.communicate()
                if cmd2.returncode == 0:
                    # Instead of running another shell command to tail -n1 and then awk
                    # the o/p for %CPU, doing it the python way.
                    for line in out.splitlines():
                        items = line.split()
                        # Have to use PID here to search for the process line since the
                        # process name is truncated if there are more than 11 chars
                        # Need to do this on the first column since other stats (Ram,
                        # swap etc can have the PID as a subset number in it.
                        if len(items) > 0 and pid == items[0]:
                            # CPU column is hardcoded here. If top changes their o/p
                            # we will need to change this!
                            cpu_percent = items[8]
                            break
            result[process] = cpu_percent
    return result

def get_load_average():
    """
    This method fetches the load average of the system from the proc
    file system. This can be captured by looking into the loadavg file in
    /proc
    Returns:
        load_avg - String of load averages (1min, 5min, 15min)
    """
    res = ''
    try:
        with open('/proc/loadavg', 'r') as f:
            contents = f.read()
            res = " ".join(contents.split()[:3])
    except IOError:
        # We return empty string if we cannot obtain the load average
        pass
    return res

if __name__ == '__main__':
    process_list = load_process_list()
    out = get_process_cpu_utilization(process_list)
    out['load_average'] = get_load_average()
    sys.stdout.write(json.dumps(out))
