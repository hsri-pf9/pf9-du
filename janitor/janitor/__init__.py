__author__ = 'Platform9'

from ConfigParser import ConfigParser
from nova_cleanup import NovaCleanup
from time import sleep
from requests import exceptions


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
            pass

        sleep(60)

