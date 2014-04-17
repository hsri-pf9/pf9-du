# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.


__author__ = 'Platform9'

"""
Controllers that service the various requests for the backbone master web
service. Handles all requests that are related to the hosts.
"""

import pecan
from pecan import abort, expose
from pecan.rest import RestController
from pecan import conf

from bbcommon.exceptions import HostNotFound

_provider_name = conf.pf9.bbone_provider
_pkg = __import__('bbmaster.%s' % _provider_name, globals(), locals())
_module = getattr(_pkg, _provider_name)
_provider = _module.provider

class IdsController(RestController):
    """ Controller for the .../ids/ request"""

    @expose('json')
    def get_all(self):
        """
        Handles request of type: GET /v1/hosts/ids/
        :return: a list of host descriptors
        :rtype: list
        """
        return _provider.get_host_ids()

class AppsController(RestController):
    """ Controller for the .../apps request """

    @expose('json')
    def get_all(self, id):
        """
        Handles request of type: GET /v1/hosts/<id>/apps
        :param str id: id of the host being queried
        :return: a dictionary of the desired configuration
        :rtype: dict
        """
        hosts = _provider.get_hosts([id])
        if not hosts:
            abort(404)

        return hosts[0]['apps']

    @expose('json')
    def put(self, id):
        """
        Handles request of type: PUT /v1/hosts/<id>/apps
        :param str id: id of the host to which this apps state is being applied
        """
        _provider.set_host_apps(id, pecan.core.state.request.json_body)


class HostAgentController(RestController):
    """
    Controller for the .../hostagent endpoint
    """
    @expose('json')
    def get_all(self, id):
        """
        Handles request of type: GET /v1/hosts/<id>/hostagent
        :param str id: id of the host being queried
        :return: a dictionary of host agent properties
        :rtype: dict
        """
        out = _provider.get_host_agent(id)
        if not out:
            abort(404)
        return out

    @expose('json')
    def put(self, id):
        """
        Handles requests of type: PUT /v1/hosts/<id>/hostagent
        :param str id: id of the host to which this hostagent is being applied
        """
        req = pecan.core.state.request.json_body
        # Some request validation
        req_keys = ("version", "url", "name")
        if not all (k in req for k in req_keys):
            # one of the expected input is missing
            abort(400)

        try:
            _provider.set_host_agent(id, req)
        except HostNotFound:
            abort(404)

class HostsController(RestController):
    """ Controller for the .../hosts endpoint"""

    ids = IdsController()
    apps = AppsController()
    hostagent = HostAgentController()

    @expose('json')
    def get_all(self):
        """
        Handles request of type: GET /v1/hosts/
        :return: a list of all host descriptors
        :rtype: dict
        """
        return _provider.get_hosts()

    @expose('json')
    def get_one(self, id):
        """
        Handles request of type: GET /v1/hosts/<id>
        :param str id: id of the host being queried
        :return: a single host descriptor
        :rtype: dict
        """
        out = _provider.get_hosts([id])
        if not out:
            abort(404)

        return out[0]

