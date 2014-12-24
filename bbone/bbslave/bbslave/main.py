# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

"""
Main entry point for backbone slave agent (a.k.a pf9-hostagent)
"""

__author__ = 'leb'


import ConfigParser
from os import environ
from bbcommon import constants
from slave import reconnect_loop

hostagent_conf = environ.get('HOSTAGENT_CONFIG_FILE',
                             constants.HOSTAGENT_CONFIG_FILE)
hostagent_override_conf = environ.get('HOSTAGENT_OVERRIDE_CONFIG_FILE',
                             constants.HOSTAGENT_OVERRIDE_CONFIG_FILE)

config = ConfigParser.ConfigParser()
config.read([hostagent_conf, hostagent_override_conf])
reconnect_loop(config)
