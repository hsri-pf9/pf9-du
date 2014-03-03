# Copyright 2014 Platform9 Systems Inc.
# All Rights reserved


__author__ = 'Platform9'

"""
This module contains the REST fronting implementation of Resource Manager.
The resource manager is in charge of keeping track of hosts approved for
pf9 use and its related information.
This module will work in conjunction with bbone to manage pf9 software
configuration on approved hosts.
"""

from pecan import abort, expose
from pecan.rest import RestController
from resmgr.resmgr_provider_mem import ResMgrMemProvider
from resmgr.resmgr_provider_pf9 import ResMgrPf9Provider
from resmgr.exceptions import RoleNotFound, ResourceNotFound

class RolesController(RestController):

    @expose('json')
    def get_all(self):
        """GET /v1/roles """
        out = provider.get_roles()

        if not out:
            abort(404)

        return out

    @expose('json')
    def get_one(self, id):
        """GET /v1/roles/<id> """
        out = provider.get_roles([id])

        if not out:
            abort(404)

        return out[id]

class HostRolesController(RestController):

    @expose('json')
    def put(self, id, roleId):
        """PUT /v1/resources/<id>/roles/<role_id>"""
        try:
            provider.add_role(id, roleId)
        except (RoleNotFound, ResourceNotFound):
            abort(404)

    @expose('json')
    def delete(self, id, roleId):
        """DELETE /v1/resources/<id>/roles/<role_id>"""
        try:
            provider.delete_role(id, roleId)
        except (RoleNotFound, ResourceNotFound):
            abort(404)

class ResourcesController(RestController):
    roles = HostRolesController()

    @expose('json')
    def get_all(self):
        """GET /v1/resources"""
        res = provider.get_resources()

        if not res:
            abort(404)

        return [val for key,val in res.iteritems()]

    @expose('json')
    def get_one(self, id):
        """GET /v1/resources/<id>"""
        out = provider.get_resources([id])

        if not out:
            abort(404)

        return out[id]

provider = ResMgrPf9Provider()

