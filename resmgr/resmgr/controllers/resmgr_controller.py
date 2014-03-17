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

import pecan
from pecan import abort, expose
from pecan.rest import RestController
from resmgr.resmgr_provider_pf9 import ResMgrPf9Provider
from resmgr.exceptions import RoleNotFound, ResourceNotFound
from enforce_policy import enforce

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
        out = _provider.get_all_roles()

        if not out:
            return []

        return [val for val in out.itervalues()]

    @expose('json')
    def get_one(self, id):
        """
        Handles request of type GET /v1/roles/<id>
        :param str id: ID of the role
        :return: dictionary of properties for the role
        :rtype: dict
        """
        out = _provider.get_role(id)

        if not out:
            abort(404)

        return out[id]


class HostRolesController(RestController):
    """Controller for hosts' roles related requests"""

    @enforce(required = ['hostadmin'])
    @expose('json')
    def put(self, id, roleId):
        """
        Handles requests of type PUT /v1/resources/<id>/roles/<role_id>
        Assigns the specified role to the resource.
        :param str id: ID of the resource
        :param str roleId: ID of the role being assigned
        """
        try:
            _provider.add_role(id, roleId)
        except (RoleNotFound, ResourceNotFound):
            abort(404)

    @enforce(required = ['hostadmin'])
    @expose('json')
    def delete(self, id, roleId):
        """
        Handles request of type DELETE /v1/resources/<id>/roles/<role_id>
        Removes the specified role from the resource
        :param str id: ID of the resource
        :param str roleId: ID of the role being assigned
        """
        try:
            _provider.delete_role(id, roleId)
        except (RoleNotFound, ResourceNotFound):
            abort(404)


class ResourcesController(RestController):
    """ Controller for resources related requests"""
    roles = HostRolesController()

    @expose('json')
    def get_all(self):
        """
        Handles requests of type GET /v1/resources. Returns all resources known
        to the resource manager.
        :return: list of resources. Empty list if no resources are present.
        :rtype: list
        """
        res = _provider.get_all_resources()

        if not res:
            return []

        return [val for val in res.itervalues()]

    @expose('json')
    def get_one(self, id):
        """
        Handles requests of type GET /v1/resources/<id>
        :return: dictionary of attributes about the resource
        :rtype: dict
        """
        out = _provider.get_resource(id)

        if not out:
            abort(404)

        return out[id]

