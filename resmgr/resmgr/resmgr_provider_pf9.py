# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved

__author__ = 'Platform9'

"""
This module provides real implementation of Resource Manager provider interface
"""

from resmgr_provider import ResMgrProvider
from exceptions import BBMasterNotFound, ResourceNotFound, RoleExists, RoleNotFound, \
    ResConfigFailed
from resmgr_provider import RState
from bbcommon.utils import is_satisfied_by
import requests
import copy
import json
from ConfigParser import ConfigParser
from time import sleep

def call_remote_service(url):
    """
    Call GET on remote URL, handle errors
    """
    try:
        r = requests.get(url)
        if r.status_code != requests.codes.ok:
            raise BBMasterNotFound('Return code: %s' % str(r.status_code))
        return r.json()

    except requests.exceptions.RequestException as re:
        raise BBMasterNotFound(re)


class RolesMgr(object):
    """
    Keeps track of available roles in the system, specific configuration needed, etc.
    """
    #json representation of roles information

    #TODO: Set correct IP and config information

    roles_data = {
        "pf9-ostackhost": {
            "id": "pf9-ostackhost",
            "name": "OpenStack Host",
            "description": "Host assigned to run OpenStack Software"
        }
    }

    def __init__(self, url, cfg, timeout=(15 * 60), sleep_time=5):
        self._bburl = url
        self._cfg = cfg
        self._timeout = timeout
        self._sleep_time = sleep_time

    @staticmethod
    def get_roles(id_list=[]):
        """
        Get public portion of roles information
        """
        if not id_list:
            id_list = RolesMgr.roles_data.keys()

        all_roles = RolesMgr.roles_data
        selected_roles = {}
        for role_id in id_list:
            if role_id not in all_roles.keys():
                continue
            selected_roles[role_id] = all_roles[role_id]

        return selected_roles

    @staticmethod
    def exists(role_id):
        return role_id in RolesMgr.roles_data

    def _prepare_app_cfg(self, cfg, remove=False):
        """
        Create role specific configuration.
        TODO: Create interface when we have multiple apps
        :param ConfigParser cfg: Global config
        :return: role specific config
        :rtype: dict
        """
        dns_name = cfg.get("DEFAULT", "DU_FQDN")
        flat_interface = "eth0"
        ostack_password = "nova"
        ostack_ver = '1.0.0-1'
        #TODO: Right now only one role "pf9-ostackhost" is hard-coded, revisit
        return {
            'pf9-ostackhost': {
                'version': ostack_ver,
                'running': True,
                'url': "http://%s/ostackhost/pf9-ostackhost-%s.x86_64.rpm" % (dns_name,
                                                                              ostack_ver),
                'config': {
                    "nova": {
                        "DEFAULT": {
                            "rabbit_host": dns_name,
                            "my_ip": dns_name,
                            "ec2_dmz_host": dns_name,
                            "glance_api_servers": "%s:9292" % dns_name,
                            "rabbit_password": ostack_password,
                            "xvpvncproxy_base_url":
                                "http://%s:6081/console" % dns_name,
                            "s3_host": dns_name,
                            "flat_interface": flat_interface,
                            "novncproxy_base_url":
                                "http://%s:6080/vnc_auto.html" % dns_name
                        },
                        "spice": {
                            "html5proxy_base_url":
                                "http://%s:6082/spice_auto.html" % dns_name
                        }
                    },
                    "api-paste": {
                        "filter:authtoken": {
                            "admin_password": ostack_password,
                            "auth_host": dns_name
                        }
                    }
                }

            }
        } if not remove else {}

    def push_configuration(self, res_id, role_id):
        """
        Push app configuration to bbone
        :param res_id: resource identifier
        """
        remove = False
        if role_id and role_id != "pf9-ostackhost":
            raise RoleNotFound(role_id)
        elif not role_id:
            remove = True

        app_info = self._prepare_app_cfg(self._cfg, remove)

        #TODO update arguments
        bbmaster_url = ''.join([self._bburl, '/v1/hosts/', res_id, '/apps'])

        try:
            installed_app_info = call_remote_service(bbmaster_url)

            if is_satisfied_by(app_info, installed_app_info):
                return

            r = requests.put(bbmaster_url, json.dumps(app_info))

            if r.status_code != requests.codes.ok:
                raise ResConfigFailed('Unexpected response: %s' % str(r.status_code))

            total_time = 0
            while total_time < self._timeout and \
                    not is_satisfied_by(app_info, installed_app_info):
                sleep(self._sleep_time)
                total_time += self._sleep_time
                installed_app_info = call_remote_service(bbmaster_url)

            # Apps did not converge
            if not is_satisfied_by(app_info, installed_app_info):
                raise ResConfigFailed('Install timeout')

        except requests.exceptions.RequestException as re:
            raise BBMasterNotFound(re)


class ResInvtMgr(object):
    """
    Keeps track of available resources in the system
    """

    def __init__(self, url, rolesMgr):
        assert url is not None
        self._url = url
        self._rolesMgr = rolesMgr
        self._known_res = {}

    def _refresh_res_ids(self, id_list=[]):
        """
        Get all new resources.
        TODO: Make this polling API running as background thread
        """
        all_ids = call_remote_service(''.join([self._url, '/v1/hosts/ids']))
        new_list = filter(lambda x: x not in id_list, all_ids)
        deleted_list = filter(lambda x: x not in all_ids, id_list)
        return new_list, deleted_list

    def _update_known_resources(self):
        """Update resource list by querying back bone"""
        existing_ids = self._known_res.keys()
        new_ids, deleted_ids = self._refresh_res_ids(existing_ids)

        for res_id in new_ids:
            res_info = call_remote_service(''.join([self._url, '/v1/hosts/', res_id]))
            self._known_res[res_id] = {
                "id": res_id,
                "state": RState.inactive,
                "info": res_info['info'],
                "roles": []
            }

        for res_id in deleted_ids:
            del self._known_res[res_id]

    def _get_res_in_brief(self, res):
        """
        Get only some in resource dict, sufficient to show as list
        """
        brief_keys = ['id', 'state', 'roles']
        ret_dict = {}
        for key in brief_keys:
            ret_dict[key] = res[key]

        return ret_dict

    def get_resources(self, id_list=[]):
        """
        Get available resources
        """
        self._update_known_resources()
        all_res = self._known_res
        brief = False

        if not id_list:
            brief = True
            id_list = all_res.keys()

        selected_res = {}
        for res_id in id_list:
            if res_id not in all_res.keys():
                continue

            selected_res[res_id] = self._get_res_in_brief(all_res[res_id]) \
                if brief else all_res[res_id]

        return selected_res

    def add_role(self, res_id, role_id):
        """
        Add new role to existing resource
        """
        if not RolesMgr.exists(role_id):
            raise RoleNotFound(role_id)

        if res_id not in self._known_res.keys():
            raise ResourceNotFound(res_id)

        if role_id in self._known_res[res_id]['roles']:
            return

        self._rolesMgr.push_configuration(res_id, role_id)

        self._known_res[res_id]['roles'].append(role_id)
        self._known_res[res_id]['state'] = RState.active

    def rem_role(self, res_id, role_id):
        """
        Remove assigned role from a resource
        """

        if res_id not in self._known_res.keys():
            raise ResourceNotFound(res_id)

        if role_id not in self._known_res[res_id]['roles']:
            raise RoleNotFound(role_id)

        self._rolesMgr.push_configuration(res_id, None)
        self._known_res[res_id]['roles'].remove(role_id)

        if not self._known_res[res_id]['roles']:
            self._known_res[res_id]['state'] = RState.inactive


class ResMgrPf9Provider(ResMgrProvider):
    """
    TODO: Make this linux-like, set common location where services can lookup info about
    each other
    """
    url = "http://localhost:8082"
    global_cfg_file = '/etc/pf9/global.conf'

    config = ConfigParser()
    config.read([global_cfg_file])
    rolesMgr = RolesMgr(url, config)
    resInvtMgr = ResInvtMgr(url, rolesMgr)

    def __init__(self):
        pass


    def get_roles(self, id_list=[]):
        return self.rolesMgr.get_roles(id_list)

    def get_resources(self, id_list=[]):
        out = self.resInvtMgr.get_resources(id_list)
        return out

    def add_role(self, res_id, role_id):
        self.resInvtMgr.add_role(res_id, role_id)

    def delete_role(self, res_id, role_id):
        self.resInvtMgr.rem_role(res_id, role_id)
