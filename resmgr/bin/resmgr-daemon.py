# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights reserved

import logging
import paste.deploy
import paste.httpserver
import os
import sys
import os.path
import time

pidfile = '/var/run/pf9/resmgr.pid'
logfile = '/var/log/pf9/resmgr-daemon.log'
pecan_config = '/etc/pf9/resmgr_config.py'
paste_ini = '/etc/pf9/resmgr-paste.ini'

logger = logging.getLogger("resmgr-daemon")
logger.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler = logging.FileHandler(logfile)
handler.setFormatter(formatter)
logger.addHandler(handler)

def makedir(dirname) :
    try:
        os.makedirs(dirname)
    except OSError :
        if not os.path.isdir(dirname) :
            logger.error("Could not create directory %s" % dirname)
            raise

def main():
    makedir(os.path.dirname(pidfile))
    logger.info('Starting the resource manager.')
    while True:
        app = paste.deploy.loadapp('config:%s' % paste_ini,
                                   global_conf = {'config' : pecan_config})
        paste.httpserver.serve(app, port = 8083)
        time.sleep(5)
        logger.error('Resource manager shutdown unexpectedly. Attempting to restart...')


if __name__ == "__main__":
    main()
