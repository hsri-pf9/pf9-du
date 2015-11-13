# Copyright 2015 Platform9 Systems Inc.
# All Rights Reserved.

# TODO: Implement interface so that new apps can follow same structure by
#       implementing it


from bbcommon.exceptions import Pf9FirmwareAppsError
import logging

logger = logging.getLogger(__name__)

__author__ = 'Platform9'


def insert_app_config(desired_apps, vmw_mgmt_cfg, host_state=None):
    """
    vmw_mgmt_cfg can be None
    """
    if not type(desired_apps) is dict:
        return desired_apps
    if not host_state:
        logger.error('host state not found. Unable to determine'
                     ' whether to add pf9-vmw-mgmt config')
        raise PF9FirmwareAppsError
    _insert_vmw_mgmt = _is_vmware_appliance(host_state)
    if _insert_vmw_mgmt and vmw_mgmt_cfg:
        desired_apps['pf9-vmw-mgmt'] = vmw_mgmt_cfg
    return desired_apps


def get_service_config():
    # This function returns the services that need to be running and other
    # config settings specific to the app
    return {
        'service_states': {},
        'config': {}
    }


def _is_vmware_appliance(host_state):
    hyp_info = host_state.get('hypervisor_info', False)
    if hyp_info:
        if hyp_info.get('hypervisor_type', 'KVM') == 'VMWareCluster' or hyp_info.get('hypervisor_type') == 'VMWareNeutron':
            return True
    return False
