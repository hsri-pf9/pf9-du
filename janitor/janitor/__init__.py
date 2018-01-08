__author__ = 'Platform9'

from ConfigParser import ConfigParser
from janitor.nova_cleanup import NovaCleanup
from janitor.glance_cleanup import GlanceCleanup
from janitor.network_cleanup import NetworkCleanup

import os
import logging
import logging.handlers
import subprocess
import requests.packages.urllib3.exceptions as urllib_exceptions

from datetime import datetime
from requests import exceptions
from time import sleep

LOG = logging.getLogger('janitor-daemon')

LOG_LEVELS = {
    'CRITICAL': logging.CRITICAL,
    'ERROR': logging.ERROR,
    'WARN': logging.WARNING,
    'INFO': logging.INFO,
    'DEBUG': logging.DEBUG,
}


def _parse_config(config_file):
    config = ConfigParser(defaults={
            'filename': '/var/log/pf9/janitor/janitor.log',
            'maxKBytes': 2048,
            'backupCount': 10
        })
    config.read(config_file)
    return config

def _setup_logging(config):
    level = config.get('log', 'level')
    level = level.upper()

    if level in LOG_LEVELS.keys():
        LOG.setLevel(LOG_LEVELS[level])
    else:
        LOG.warning('Ignoring invalid level %s', level)

    logfile = config.get('log', 'filename')
    maxBytes = 1024 * config.getint('log', 'maxKBytes')
    backupCount = config.getint('log', 'backupCount')

    logdir = os.path.dirname(logfile)
    if not os.path.isdir(logdir):
        os.makedirs(logdir)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s '
                                  '- %(message)s')
    handler = logging.handlers.RotatingFileHandler(logfile, maxBytes=maxBytes,
                                                   backupCount=backupCount)
    handler.setFormatter(formatter)
    LOG.addHandler(handler)
    LOG.info('##############################')
    LOG.info('Starting janitor at %s', datetime.now())

def _run_command(command, stdout=subprocess.PIPE):
    proc = subprocess.Popen(command, shell=True,
                            stdin=subprocess.PIPE,
                            stdout=stdout,
                            stderr=subprocess.PIPE)
    out, err = proc.communicate()
    code = proc.returncode
    return code, out, err


def check_for_neutron():
    code, out, err = _run_command("/bin/crudini --get /etc/nova/nova.conf DEFAULT network_api_class")
    LOG.info("Neutron check output, code=%d stdout=%s stderr=%s", code, out, err)
    return code == 0 and out.strip() == "nova.network.neutronv2.api.API"

def serve(config_file):
    """
    Run a bunch of periodic background tasks

    :param: config_file Janitor config file
    """
    while True:
        try:
            cfg = _parse_config(config_file)
            _setup_logging(cfg)

            nova_obj = NovaCleanup(conf=cfg)
            glance_obj = GlanceCleanup(conf=cfg)
            nw_obj = NetworkCleanup(conf=cfg)
            break
        except Exception as e:
            LOG.error('Unexpected error during init: %s', e)

        sleep(int(cfg.get('DEFAULT', 'pollInterval')))

    neutron_present = check_for_neutron()

    while True:
        try:
            glance_obj.cleanup()
            # pshanbhag:
            # See IAAS-5438. To avoid janitor triggering a VM network cleanup, we
            # will temporarily make janitor do nothing on Neutron setups. This can
            # go away once we have a good fix in place for IAAS-5438
            # sarun: We are not going to do nova, nova  network cleanup.
            # Opening  up glance cleanup.
            if not neutron_present:
                nova_obj.cleanup()
                nw_obj.cleanup()
        except (exceptions.ConnectionError, urllib_exceptions.ProtocolError) as e:
            LOG.info('Connection error: {err}, will retry in a bit'.format(err=e))
        except RuntimeError as e:
            LOG.error('Unexpected error %s', e)

        sleep(int(cfg.get('DEFAULT', 'pollInterval')))

