# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights reserved

from daemon.runner import DaemonRunner, DaemonRunnerStopFailureError
import argparse
import logging
import paste.deploy
import paste.httpserver
import os
import sys
import os.path
import time

pidfile = '/var/run/pf9/resmgr.pid'
logfile = '/var/log/pf9/resmgr-daemon.log'
outfile ='/var/log/pf9/resmgr-out.log'
pecan_config = '/etc/pf9/resmgr_config.py'
paste_ini = '/etc/pf9/resmgr-paste.ini'

logger = logging.getLogger("resmgr-daemon")
logger.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler = logging.FileHandler(logfile)
handler.setFormatter(formatter)
logger.addHandler(handler)

class ResmgrDaemon():

    def __init__(self):
        self.stdin_path = '/dev/null'
        self.stdout_path = outfile
        self.stderr_path = outfile
        self.pidfile_path = pidfile
        self.pidfile_timeout = 5

    def run(self):
        logger.info('Starting the resource manager.')
        while True:
            app = paste.deploy.loadapp('config:%s' % paste_ini,
                                       global_conf = {'config' : pecan_config})
            paste.httpserver.serve(app, port = 8083)
            time.sleep(5)
            logger.error('Resource manager shutdown unexpectedly. Attempting to restart...')

def makedir(dirname) :
    try:
        os.makedirs(dirname)
    except OSError :
        if not os.path.isdir(dirname) :
            logger.error("Could not create directory %s" % dirname)
            raise

def main():
    parser = argparse.ArgumentParser(description='Resource manager flags.')
    parser.add_argument('--no-daemon', action='store_true', default=False,
                        help='Do not run resource manager as a daemon.')

    arguments, _ = parser.parse_known_args()

    resmgr = ResmgrDaemon()

    if arguments.no_daemon:
        try:
            resmgr.run()
        except KeyboardInterrupt:
            # Exit after resmgr.run() completes
            sys.exit(1)
        finally:
            sys.exit(1)
    else:
        runner = DaemonRunner(resmgr)

        # ensures that the logger file handle does not get closed during daemonization
        runner.daemon_context.files_preserve = [handler.stream]
        makedir(os.path.dirname(pidfile))
        try:
            runner.do_action()
        except DaemonRunnerStopFailureError:
            sys.exit(0)

if __name__ == "__main__":
    main()
