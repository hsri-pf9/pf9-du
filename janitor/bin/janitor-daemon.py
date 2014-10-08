# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights reserved

from daemon.runner import DaemonRunner, DaemonRunnerStopFailureError
import os
import sys
import os.path
import time
from janitor import serve

pidfile = '/var/run/pf9/janitor.pid'
outfile ='/var/log/pf9/janitor-out.log'
configfile = '/etc/pf9/janitor.conf'

class JanitorDaemon():

    def __init__(self):
        self.stdin_path = '/dev/null'
        self.stdout_path = outfile
        self.stderr_path = outfile
        self.pidfile_path = pidfile
        self.pidfile_timeout = 5

    def run(self):
        sys.stdout.write('Starting the janitor service.\n')

        while True:
            serve(configfile)

            time.sleep(5)
            sys.stderr.write('Janitor shutdown unexpectedly. Attempting to restart...\n')


def makedir(dirname):
    try:
        os.makedirs(dirname)
    except OSError:
        if not os.path.isdir(dirname):
            sys.stderr.write("Could not create directory %s\n" % dirname)
            raise

janitor = JanitorDaemon()
runner = DaemonRunner(janitor)

makedir(os.path.dirname(pidfile))
try:
    runner.do_action()
except DaemonRunnerStopFailureError:
    sys.exit(1)

