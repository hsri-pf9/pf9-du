# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'leb'

import copy
from configutils import configutils
from ConfigParser import ConfigParser
import ssl

def is_satisfied_by(desired_config, current_config):
    """
    Determines whether the desired overall app configuration
    is satisfied by the current configuration.

    :param dict desired_config: desired configuration
    :param dict current_config: current configuration
    :rtype: bool
    """

    # It is possible for bbmaster to pass None as the desired config.
    # This happens when receiving a status message from a slave before
    # any client has expressed a desired config via REST API.
    # Note: an empty desired_config has a different meaning:
    # no pf9 apps shall be installed.
    if desired_config is None:
        return True

    specified_config = copy.deepcopy(desired_config)
    # First, the set of application names must be identical
    if set(specified_config.keys()) != set(current_config.keys()):
        return False
    # Second, the app properties and configurations must match
    for app_name, app_spec in specified_config.iteritems():
        # Remove url because it doesn't truly belong in the state
        if 'url' in app_spec:
            del app_spec['url']
        if not configutils.is_dict_subset(app_spec, current_config[app_name]):
            return False
    return True

def get_ssl_options(config):
    """
    Obtains SSL options from a config file.
    :param ConfigParser config: The ConfigParser-like object
    :return: A dictionary of SSL options if SSL is enabled, else None
    """
    return {
            'certfile': config.get('ssl', 'certfile'),
            'keyfile': config.get('ssl', 'keyfile'),
            'ca_certs': config.get('ssl', 'ca_certs'),
            "cert_reqs": ssl.CERT_REQUIRED
    } if config.has_option('ssl', 'certfile') else None
