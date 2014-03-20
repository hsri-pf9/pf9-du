# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved

__author__ = 'Platform9'

"""
This module provides real implementation of Resource Manager provider interface
"""

import ConfigParser
import json
import time

import requests

from bbcommon.utils import is_satisfied_by
from dbutils import ResMgrDB
from exceptions import BBMasterNotFound, ResourceNotFound, RoleNotFound, ResConfigFailed
from resmgr_provider import ResMgrProvider, RState


def call_remote_service(url):
    """
    Call GET on remote URL, handle errors
    :param str url: URL endpoint to be invoked
    :return: JSON representation of the response
    :rtype: dict
    """
    try:
        r = requests.get(url)
        if r.status_code != requests.codes.ok:
            raise BBMasterNotFound('Return code: %s' % str(r.status_code))
        return r.json()

    except requests.exceptions.RequestException as e:
        raise BBMasterNotFound(e)


class RolesMgr(object):
    """
    Keeps track of available roles in the system, specific configuration needed, etc.
    """

    def __init__(self, config, db_handler):
        """
        Constructor
        :param ConfigParser config: ConfigParser object for resource manager configuration
        :param ResMgrDB db_handler: Object handler to the resource manager DB
        """
        self.config = config
        self.bb_url = config.get('backbone', 'endpointURI')
        self.req_timeout = config.getint('backbone', 'requestTimeout')
        self.req_sleep_interval = config.getint('backbone', 'requestWaitPeriod')
        self.db_handler = db_handler

    def get_all_roles(self):
        """
        Returns information of all known roles
        :rtype: dict
        """
        query_op = self.db_handler.query_roles()
        result = {}
        for role in query_op:
            role_attrs = {
                'id': role.rolename,
                'name': role.name,
                'description': role.description
            }
            result[role.rolename] = role_attrs

        return result

    def get_role(self, role_id):
        """
        Get public portion of roles information for a role
        :param str role_id: ID of the role
        :return: Dictionary of the role attributes
        :rtype: dict
        """
        role = self.db_handler.query_role(role_id)
        result = {
            role.rolename: {
                'id': role.rolename,
                'name': role.name,
                'description': role.description
            }
        }

        return result

    def exists(self, role_id):
        """
        Check if a role exists
        :param role_id: ID of the role
        :return: True if role exists, else False
        :rtype: bool
        """
        return self.db_handler.query_role(role_id) is not None

    def _prepare_app_cfg(self, roles):
        """
        Create role specific configuration.
        TODO: Create interface when we have multiple apps
        :param list roles: list of roles
        :return: role specific config
        :rtype: dict
        :raises RoleNotFound: if the specified role is not present
        """
        app_config = {}
        for role in roles:
            # TODO: Right now, only ostackhost role is supported. Need to make
            # this generic in future
            if role != 'pf9-ostackhost':
                raise RoleNotFound(role)
            role_config = self.db_handler.query_role(role).desiredconfig
            global_cfg_file = self.config.get('resmgr', 'global_config_file')
            global_cfg = ConfigParser.ConfigParser()
            global_cfg.read(global_cfg_file)
            param_vals = {
                'du_host': global_cfg.get("DEFAULT", "DU_FQDN"),
                'interface': "eth0",
                'ostack_password': "m1llenn1umFalc0n",
                'version': '1.0.0-1'
            }
            config_str = role_config % param_vals
            app_config[role] = json.loads(config_str)

        return app_config

    def push_configuration(self, host_id, roles):
        """
        Push app configuration to backbone service
        :param str host_id: host identifier
        :param list roles: list of role IDs that need to be set
        :raises ResConfigFailed: if setting the configuration fails or times out
        :raises BBMasterNotFound: if communication to the backbone fails
        """
        app_info = self._prepare_app_cfg(roles)

        url = "%s/v1/hosts/%s/apps" % (self.bb_url, host_id)

        try:
            installed_app_info = call_remote_service(url)

            if is_satisfied_by(app_info, installed_app_info):
                return

            r = requests.put(url, json.dumps(app_info))

            if r.status_code != requests.codes.ok:
                raise ResConfigFailed('Unexpected response: %d' % r.status_code)

            total_time = 0
            while total_time < self.req_timeout and \
                    not is_satisfied_by(app_info, installed_app_info):
                time.sleep(self.req_sleep_interval)
                total_time += self.req_sleep_interval
                installed_app_info = call_remote_service(url)

            # Apps did not converge
            if not is_satisfied_by(app_info, installed_app_info):
                raise ResConfigFailed('Install timeout')

        except requests.exceptions.RequestException as re:
            raise BBMasterNotFound(re)


class HostInventoryMgr(object):
    """
    Keeps track of available hosts in the system
    """

    def __init__(self, config, db_handler):
        """
        Constructor
        :param ConfigParser config: ConfigParser object for resource manager configuration
        :param ResMgrDB db_handler: Object handler to the resource manager DB
        """
        self.db_handler = db_handler
        self.bbone_url = config.get("backbone", "endpointURI")
        self.sleep_time = config.get("backbone", "requestWaitPeriod")
        self.timeout = config.get("backbone", "requestTimeout")

    def _refresh_host_ids(self, id_list=[]):
        """
        Get all latest set of hosts.
        TODO: Make this polling API running as background thread
        :param list id_list: List of existing host ids
        :return: lists of new and deleted host ids
        :rtype: tuple (of lists)
        """
        all_ids = call_remote_service(''.join([self.bbone_url, '/v1/hosts/ids']))
        new_list = filter(lambda x: x not in id_list, all_ids)
        deleted_list = filter(lambda x: x not in all_ids, id_list)
        return new_list, deleted_list

    def _update_known_hosts(self):
        """
        Update host list by querying back bone. Updates the database with
        the latest state of hosts.
        """
        query_op = self.db_handler.query_hosts()
        existing_ids = []
        for host in query_op:
            existing_ids.append(host.id)

        new_ids, deleted_ids = self._refresh_host_ids(existing_ids)

        for host_id in new_ids:
            host_info = call_remote_service('%s/v1/hosts/%s' % (self.bbone_url,
                                                                host_id))
            self.db_handler.add_new_host(host_id, host_info['info'])

        for host_id in deleted_ids:
            self.db_handler.delete_host(host_id)

    def get_all_hosts(self):
        """
        Returns information about all known hosts.
        :rtype: dict:
        """
        self._update_known_hosts()
        query_op = self.db_handler.query_hosts()
        result = {}
        for host in query_op:
            cur_roles = []
            for role in host.roles:
                cur_roles.append(role.rolename)

            host_attrs = {
                'id': host.id,
                'roles': cur_roles,
                'state': RState.active if cur_roles else RState.inactive
            }
            result[host.id] = host_attrs

        return result


    def get_host(self, host_id):
        """
        Get information for a host
        :param str host_id: ID of the host
        :return: dictionary of the host attributes
        :rtype: dict
        """
        self._update_known_hosts()
        host = self.db_handler.query_host(host_id)
        cur_roles = []
        for role in host.roles:
            cur_roles.append(role.rolename)

        result = {
            host.id: {
                'id': host.id,
                'roles': cur_roles,
                'state': RState.active if cur_roles else RState.inactive,
                'info' : {
                    'hostname': host.hostname,
                    'os_family': host.hostosfamily,
                    'arch': host.hostarch,
                    'os_info': host.hostosinfo
                }
            }
        }

        return result



class ResMgrPf9Provider(ResMgrProvider):
    """
    Implementation of the ResMgrProvider interface
    """
    def __init__(self, config_file):
        """
        Constructor
        :param str config_file: Path to configuration file for resource manager
        """
        config = ConfigParser.ConfigParser()
        config.read(config_file)
        db_uri = config.get('database', 'sqlconnectURI')
        self.res_mgr_db = ResMgrDB(db_uri)
        self.host_inventory_mgr = HostInventoryMgr(config, self.res_mgr_db)
        self.roles_mgr = RolesMgr(config, self.res_mgr_db)

    def get_all_roles(self):
        """
        Returns information about all known roles
        :return: dictionary of roles and their information
        :rtype: dict
        """
        return self.roles_mgr.get_all_roles()

    def get_role(self, role_id):
        """
        Returns all information about a role
        :param str role_id: ID of the role
        :return: dictionary of the role information
        :rtype: dict
        """
        return self.roles_mgr.get_role(role_id)

    def get_all_resources(self):
        """
        Returns information about all known resources
        :return: dictionary of resources and their information
        :rtype: dict
        """
        return self.host_inventory_mgr.get_all_hosts()

    def get_resource(self, resource_id):
        """
        Returns all information about a resource
        :param resource_id: ID of the resource
        :return: dictionary of the resource information
        :rtype: dict
        """
        return self.host_inventory_mgr.get_host(resource_id)

    def add_role(self, res_id, role_id):
        """
        Add a role to a particular resource
        :param str res_id: ID of the resource
        :param str role_id: ID of the role
        :raises RoleNotFound: if the role is not present
        :raises ResourceNotFound: if the resource is not present
        :raises ResConfigFailed: if setting the configuration fails or times out
        :raises BBMasterNotFound: if communication to the backbone fails
        """
        if not self.roles_mgr.exists(role_id):
            raise RoleNotFound(role_id)

        resource_inst = self.get_resource(res_id)
        if not resource_inst:
            raise ResourceNotFound(res_id)

        if role_id in resource_inst[res_id]['roles']:
            return

        self.roles_mgr.push_configuration(res_id, [role_id])
        self.res_mgr_db.associate_role_to_host(res_id, role_id)

    def delete_role(self, res_id, role_id):
        """
        Disassociates a role from a resource.
        :param str res_id: ID of the resource
        :param str role_id: ID of the role
        :raises RoleNotFound: if the role is not present
        :raises ResourceNotFound: if the resource is not present
        :raises ResConfigFailed: if setting the configuration fails or times out
        :raises BBMasterNotFound: if communication to the backbone fails
        """
        if not self.roles_mgr.exists(role_id):
            raise RoleNotFound(role_id)

        resource_inst = self.get_resource(res_id)
        if not resource_inst:
            raise ResourceNotFound(res_id)

        if role_id not in resource_inst[res_id]['roles']:
            return

        resource_inst[res_id]['roles'].remove(role_id)
        self.roles_mgr.push_configuration(res_id, resource_inst[res_id]['roles'])
        self.res_mgr_db.remove_role_from_host(res_id, role_id)


def get_provider(config_file):
    return ResMgrPf9Provider(config_file)
