__author__ = 'Platform9'

from ConfigParser import ConfigParser
from nova_cleanup import NovaCleanup
import threading


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

    threading.Timer(60, nova_obj.cleanup_hosts).start()
