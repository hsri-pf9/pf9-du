__author__ = 'Platform9'

from ConfigParser import ConfigParser
from nova_cleanup import NovaCleanup
from time import sleep


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
        nova_obj.cleanup_hosts()
        sleep(60)

