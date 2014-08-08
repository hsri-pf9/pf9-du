__author__ = 'Platform9'

from ConfigParser import ConfigParser
from nova_cleanup import NovaCleanup
from time import sleep
from requests import exceptions
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

    while True:
        try:
            nova_obj.cleanup()
        except exceptions.ConnectionError:
            LOG.info('Keystone service unavailable, will retry in a bit')
        except RuntimeError as e:
            LOG.error('Unexpected error %s', e)

        sleep(60)

