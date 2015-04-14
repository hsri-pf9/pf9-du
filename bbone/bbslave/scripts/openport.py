# Copyright (c) 2014 Platform9 systems. All rights reserved

from __future__ import print_function

import os
import subprocess
import sys

def find_rule(portnum):
    cmd = ['iptables', '-L', 'INPUT', '-n', '--line-numbers']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    retcode = proc.wait()
    if retcode != 0:
        error = proc.stderr.read()
        print('Error getting iptables list: %s' % error, file=sys.stderr)
        raise subprocess.CalledProcessError(retcode, cmd)
    else:
        output = proc.stdout.read()
        for line in output.splitlines():
            if line.find('ACCEPT') >= 0 and \
               line.find('tcp') >= 0 and \
               line.find('dpt:%d' % portnum) >= 0:
                linenum = line.split()[0]
                return linenum
        return None

def remove_rule(rulenum):
    subprocess.check_call(['iptables', '-D', 'INPUT', str(rulenum)])

def add_rule(portnum):
    subprocess.check_call(['iptables', '-I', 'INPUT', '-p', 'tcp',
        '--dport', str(portnum), '-j', 'ACCEPT'])

def save_rules():
    """
    Attempt to make the current rules persistent.
    """
    if os.path.isfile('/etc/init.d/iptables'):
        subprocess.check_call(['/etc/init.d/iptables', 'save'])
    elif os.path.isfile('/etc/init.d/iptables-persistent'):
        subprocess.check_call(['/etc/init.d/iptables-persistent', 'save'])
    else:
        print('Warning: no iptables init.d script found. iptables changes '
              'are not persistent')

def main():
    if not len(sys.argv) == 3:
        print('Please provide a command (add,remove) and a port number',
              file=sys.stderr)
        return 1
    command = sys.argv[1]
    try:
        portnum = int(sys.argv[2])
    except ValueError:
        print('Port must be a number, not %s' % sys.argv[2], file=sys.stderr)
        return 1

    try:
        if command == 'add':
            rulenum = find_rule(portnum)
            if rulenum:
                print('iptables rule already exists for port %d' % portnum)
            else:
                add_rule(portnum)
                save_rules()
                print('added iptables rule for incoming tcp port %d' %
                      portnum)
        elif command == 'remove':
            rulenum = find_rule(portnum)
            if rulenum:
                remove_rule(rulenum)
                save_rules()
                print('removed iptables rule for port %d' % portnum)
            else:
                print('no iptables rule found for port %d, no need to remove'
                      % portnum)
        return 0
    except subprocess.CalledProcessError as e:
        print('Error in openport: %s' % e, file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())
