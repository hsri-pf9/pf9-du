__author__ = 'Platform9'

from ConfigParser import ConfigParser
from janitor.nova_cleanup import NovaCleanup
from janitor.glance_cleanup import GlanceCleanup
from janitor.network_cleanup import NetworkCleanup
from janitor.alarms import AlarmsManager

import subprocess
from time import sleep
from requests import exceptions
import requests.packages.urllib3.exceptions as urllib_exceptions
import logging
import logging.handlers

logfile = '/var/log/pf9/janitor-daemon.log'
LOG = logging.getLogger('janitor-daemon')

LOG_LEVELS = {
    'CRITICAL': logging.CRITICAL,
    'ERROR': logging.ERROR,
    'WARN': logging.WARNING,
    'INFO': logging.INFO,
    'DEBUG': logging.DEBUG,
}


def _parse_config(config_file):
    config = ConfigParser()
    config.read(config_file)

    return config


def _setup_logging(config):
    level = config.get('log', 'level')
    level = level.upper()

    if level in LOG_LEVELS.keys():
        LOG.setLevel(LOG_LEVELS[level])
    else:
        LOG.warning('Ignoring invalid level %s', level)

    file_size_kb = config.get('log', 'size', 20)
    backup_files = config.get('log', 'rotate', 1024)

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler = logging.handlers.RotatingFileHandler(logfile, maxBytes=file_size_kb * 1024,
                                                   backupCount=backup_files)
    handler.setFormatter(formatter)
    LOG.addHandler(handler)


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
    cfg = _parse_config(config_file)
    _setup_logging(cfg)

    nova_obj = NovaCleanup(conf=cfg)
    glance_obj = GlanceCleanup(conf=cfg)
    nw_obj = NetworkCleanup(conf=cfg)
    alarm_obj = AlarmsManager(conf=cfg)

    neutron_present = check_for_neutron()

    while True:
        # pshanbhag:
        # See IAAS-5438. To avoid janitor triggering a VM network cleanup, we
        # will temporarily make janitor do nothing on Neutron setups. This can
        # go away once we have a good fix in place for IAAS-5438
        if not neutron_present:
            try:
                nova_obj.cleanup()
                glance_obj.cleanup()
                nw_obj.cleanup()
                alarm_obj.manage()
            except (exceptions.ConnectionError, urllib_exceptions.ProtocolError) as e:
                LOG.info('Connection error: {err}, will retry in a bit'.format(err=e))
            except RuntimeError as e:
                LOG.error('Unexpected error %s', e)

        sleep(int(cfg.get('DEFAULT', 'pollInterval')))

