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

    def __init__(self, show_comms=False):
        super(RestController, self).__init__()
        self.show_comms = show_comms

    @expose('json')
    def get_all(self, id):
        """
        Handles request of type: GET /v1/hosts/<id>/apps
        :param str id: id of the host being queried
        :return: a dictionary of the desired configuration
        :rtype: dict
        """
        hosts = _provider.get_hosts([id], self.show_comms)
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

class SupportBundleController(RestController):
    """ Controller for the .../support/ request"""

    @expose('json')
    def post(self, host_id):
        """
        Handles request of type: POST /v1/hosts/<host_id>/support/bundle
        """
        if not _provider.get_hosts([host_id]):
            abort(404)
        _provider.request_support_bundle(host_id)

class SupportCommandController(RestController):
    """ Controller for the .../support/command request"""

    @expose('json')
    def post(self, host_id):
        """
        Handles request of type: POST /v1/hosts/<host_id>/support/command
        Example JSON body: {'command' : '<command to run>'}
        """
        if not _provider.get_hosts([host_id]):
            abort(404)
        msg_body = pecan.core.state.request.json_body
        if 'command' in msg_body and len(msg_body) == 1:
            _provider.run_support_command(host_id, msg_body['command'])
        else:
            # Malformed json body
            abort(400)

class SupportController(RestController):
    """ Controller for the .../support/ request"""
    bundle = SupportBundleController()
    command = SupportCommandController()

class HostsController(RestController):
    """ Controller for the .../hosts endpoint"""

    ids = IdsController()
    apps = AppsController()
    apps_internal = AppsController(show_comms=True)
    hostagent = HostAgentController()
    support = SupportController()

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

