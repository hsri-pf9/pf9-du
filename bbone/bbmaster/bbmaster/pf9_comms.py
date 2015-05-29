# Copyright 2015 Platform9 Systems Inc.
# All Rights Reserved.

# TODO: Implement interface so that new apps can follow same structure by
#       implementing it


def insert_app_config(desired_apps, comms_cfg, host_state=None):
    """
    host_state is ignored. Needed here for maintaining
    compatibility across firmware apps.
    Inserts the specified pf9-comms configuration into the supplied dictionary.
    """
    if type(desired_apps) is dict:
        desired_apps['pf9-comms'] = comms_cfg
    return desired_apps


def get_service_config():
    # This function returns the services that need to be running and other
    # config settings specific to the app
    return {
        'running': True,
        'config': {}
    }