__author__ = 'Platform9'

from ConfigParser import ConfigParser
from janitor.nova_cleanup import NovaCleanup
from janitor.glance_cleanup import GlanceCleanup
from time import sleep
from requests import exceptions
import requests.packages.urllib3.exceptions as urllib_exceptions
import logging

LOG = logging.getLogger('janitor-daemon')


def _parse_config(config_file):
    config = ConfigParser()
    config.read(config_file)

    return config


def serve(config_file):
    """
    Run a bunch of periodic background tasks

    :param: config_file Janitor config file
    """
    cfg = _parse_config(config_file)
    nova_obj = NovaCleanup(conf=cfg)
    glance_obj = GlanceCleanup(conf=cfg)

    while True:
        try:
            nova_obj.cleanup()
            glance_obj.cleanup()
        except (exceptions.ConnectionError, urllib_exceptions.ProtocolError):
            LOG.info('Keystone service unavailable, will retry in a bit')
        except RuntimeError as e:
            LOG.error('Unexpected error %s', e)

        sleep(int(cfg.get('DEFAULT', 'pollInterval')))

