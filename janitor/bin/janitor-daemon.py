# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights reserved

from daemon.runner import DaemonRunner, DaemonRunnerStopFailureError
import logging
import os
import sys
import os.path
import time
from janitor import serve

pidfile = '/var/run/pf9/janitor.pid'
logfile = '/var/log/pf9/janitor-daemon.log'
outfile ='/var/log/pf9/janitor-out.log'
configfile = '/etc/pf9/janitor.conf'

logger = logging.getLogger("janitor-daemon")
logger.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler = logging.FileHandler(logfile)
handler.setFormatter(formatter)
logger.addHandler(handler)


class JanitorDaemon():

    def __init__(self):
        self.stdin_path = '/dev/null'
        self.stdout_path = outfile
        self.stderr_path = outfile
        self.pidfile_path = pidfile
        self.pidfile_timeout = 5

    def run(self):
        logger.info('Starting the janitor service.')

        while True:
            serve(configfile)

            time.sleep(5)
            logger.error('Janitor shutdown unexpectedly. Attempting to restart...')


def makedir(dirname):
    try:
        os.makedirs(dirname)
    except OSError:
        if not os.path.isdir(dirname):
            logger.error("Could not create directory %s" % dirname)
            raise

janitor = JanitorDaemon()
runner = DaemonRunner(janitor)

# ensures that the logger file handle does not get closed during daemonization
runner.daemon_context.files_preserve = [handler.stream]
makedir(os.path.dirname(pidfile))
try:
    runner.do_action()
except DaemonRunnerStopFailureError:
    sys.exit(1)

