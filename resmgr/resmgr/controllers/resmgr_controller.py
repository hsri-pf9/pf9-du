# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights reserved


__author__ = 'Platform9'

"""
This module contains the REST fronting implementation of Resource Manager.
The resource manager is in charge of keeping track of hosts approved for
pf9 use and its related information.
This module will work in conjunction with bbone to manage pf9 software
configuration on approved hosts.
"""

import logging
import pecan
from pecan import abort, expose
from pecan.rest import RestController
from resmgr.exceptions import RoleNotFound, HostNotFound, HostConfigFailed, BBMasterNotFound
from enforce_policy import enforce


log = logging.getLogger('resmgr')
_resmgr_conf_file = pecan.conf.resmgr['config_file']
_provider_name = pecan.conf.resmgr['provider']
_pkg = __import__('resmgr.%s' % _provider_name, globals(), locals())
_module = getattr(_pkg, _provider_name)
_provider = _module.get_provider(_resmgr_conf_file)


class RolesController(RestController):
    """ Controller for roles related requests"""

    @expose('json')
    def get_all(self):
        """
        Handles request of type GET /v1/roles
        :return: a list of available roles
        :rtype: list
        """
        log.debug('Getting all roles')
        out = _provider.get_all_roles()

        if not out:
            log.info('No roles present')
            return []

        return [val for val in out.itervalues()]

    @expose('json')
    def get_one(self, name):
        """
        Handles request of type GET /v1/roles/<role_name>
        :param str name: Name of the role
        :return: dictionary of properties for the role
        :rtype: dict
        """
        log.debug('Getting details for role %s', name)
        out = _provider.get_role(name)

        if not out:
            log.error('No matching role found for %s', name)
            abort(404)

        return out[name]


class HostRolesController(RestController):
    """Controller for hosts' roles related requests"""

    @enforce(required = ['admin'])
    @expose('json')
    def put(self, host_id, role_name):
        """
        Handles requests of type PUT /v1/hosts/<host_id>/roles/<role_name>
        Assigns the specified role to the host.
        :param str host_id: ID of the host
        :param str role_name: Name of the role being assigned
        """
        log.debug('Assigning role %s to host %s', role_name, host_id)
        try:
            _provider.add_role(host_id, role_name)
        except (RoleNotFound, HostNotFound):
            log.exception('Role %s or Host %s not found', role_name, host_id)
        except (HostConfigFailed, BBMasterNotFound):
            log.exception('Role assignment failed')
            abort(500)


    @enforce(required = ['admin'])
    @expose('json')
    def delete(self, host_id, role_name):
        """
        Handles request of type DELETE /v1/hosts/<host_id>/roles/<role_name>
        Removes the specified role from the host
        :param str host_id: ID of the host
        :param str role_name: Name of the role being assigned
        """
        log.debug('Removing role %s from host %s', role_name, host_id)
        try:
            _provider.delete_role(host_id, role_name)
        except (RoleNotFound, HostNotFound):
            log.exception('Role %s or Host %s not found', role_name, host_id)
        except (HostConfigFailed, BBMasterNotFound):
            log.exception('Role removal failed')
            abort(500)


class HostsController(RestController):
    """ Controller for hosts related requests"""
    roles = HostRolesController()

    @expose('json')
    def get_all(self):
        """
        Handles requests of type GET /v1/hosts. Returns all hosts known
        to the resource manager.
        :return: list of hosts. Empty list if no hosts are present.
        :rtype: list
        """
        log.debug('Getting details for all hosts')
        res = _provider.get_all_hosts()

        if not res:
            log.info('No hosts present')
            return []

        return [val for val in res.itervalues()]

    @expose('json')
    def get_one(self, host_id):
        """
        Handles requests of type GET /v1/hosts/<id>
        :return: dictionary of attributes about the host
        :rtype: dict
        """
        log.debug('Getting details for host %s', host_id)
        out = _provider.get_host(host_id)

        if not out:
            log.error('No matching host found for %s', host_id)
            abort(404)

        return out

    @enforce(required= ['admin'])
    @expose('json')
    def delete(self, host_id):
        """
        Handles requests of type DELETE /v1/hosts/<id>
        :param str host_id: ID of host to be removed
        """
        log.debug('Deleting host %s', host_id)
        try:
            _provider.delete_host(host_id)
        except HostNotFound:
            log.exception('No matching host found for %s', host_id)
            abort(404)
        except (HostConfigFailed, BBMasterNotFound):
            log.exception('Host delete operation failed')
            abort(500)