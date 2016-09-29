# Copyright (c) 2014 Platform9 Systems Inc. All Rights reserved

# pylint: disable=no-self-use,unused-wildcard-import,wildcard-import
# pylint: disable=too-few-public-methods,broad-except

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
from resmgr.controllers.enforce_policy import enforce
from resmgr.exceptions import *

log = logging.getLogger(__name__)
_resmgr_conf_file = pecan.conf.resmgr['config_file']
_provider_name = pecan.conf.resmgr['provider']
_pkg = __import__('resmgr.%s' % _provider_name, globals(), locals())
_module = getattr(_pkg, _provider_name)
_provider = _module.get_provider(_resmgr_conf_file)

def _json_error_response(response, code, exc):
    """
    json response from an exception object
    """
    response.status = code
    response.content_type = 'application/json'
    response.charset = 'utf-8'
    response.json = {'message': '%s: %s' % (exc.__class__.__name__, exc.msg)}
    return response

class RoleAppVersionsController(RestController):
    """Controller for role app version related requests"""

    @expose('json')
    def get(self, name):
        """
        Handles request of type GET /v1/roles/<role_name>/apps/versions
        :param str name: Name of the role
        :return: dictionary of app names and versions
        :rtype: dict
        """
        log.info('Getting app version details for role %s', name)
        out = _provider.get_app_versions(name)
        if not out:
            log.error('No matching app versions found for role %s', name)
            abort(404)

        return out

class RoleAppsController(RestController):
    """Controller for role app related requests"""
    versions = RoleAppVersionsController()

class RolesController(RestController):
    """ Controller for roles related requests"""
    apps = RoleAppsController()

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

    @enforce(required=['admin'])
    @expose('json')
    def put(self, host_id, role_name):
        """
        Handles requests of type PUT /v1/hosts/<host_id>/roles/<role_name>
        Assigns the specified role to the host.
        The body must either be empty or a Json dictionary.
        :param str host_id: ID of the host
        :param str role_name: Name of the role being assigned
        """
        msg_body = pecan.request.body
        if len(msg_body) == 0:
            msg_body = {}
        else:
            try:
                msg_body = pecan.request.json_body
            except Exception as e:
                abort(400, str(e))

        if not isinstance(msg_body, dict):
            abort(400, 'Invalid Json body')

        log.debug('Assigning role %s to host %s with message body %s',
                  role_name, host_id, msg_body)
        try:
            _provider.add_role(host_id, role_name, msg_body)
        except (RoleNotFound, HostNotFound):
            log.exception('Role %s or Host %s not found', role_name, host_id)
            abort(404)
        except (HostConfigFailed, BBMasterNotFound,
                RabbitCredentialsConfigureError):
            log.exception('Role assignment failed')
            abort(500)
        except RoleUpdateConflict as e:
            log.exception('Role assignment failed')
            return _json_error_response(pecan.response, 409, e)
        except DuConfigError as e:
            log.exception('Role assignment failed')
            return _json_error_response(pecan.response, 400, e)

    @enforce(required=['admin'])
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
        except RoleUpdateConflict as e:
            log.exception('Role removal failed')
            return _json_error_response(pecan.response, 409, e)
        except DuConfigError as e:
            log.exception('Role removal failed')
            return _json_error_response(pecan.response, 400, e)

    @expose('json')
    def get(self, host_id, role_name):
        """
        Handles requests of type GET /v1/hosts/<host_id>/roles/<role_name>
        Returns the custom role settings of the specified host
        :param str host_id: ID of the host
        :param str role_name: Name of the role to get settings for
        """
        try:
            return _provider.get_custom_settings(host_id, role_name)
        except (RoleNotFound, HostNotFound):
            log.exception('Role %s or Host %s not found', role_name, host_id)
            abort(404)
        except (HostConfigFailed, BBMasterNotFound):
            log.exception('Getting custom settings failed')
            abort(404)

class HostSupportBundleController(RestController):

    @enforce(required=['admin'])
    @expose('json')
    def post(self, host_id):
        """
        Handles requests of type POST /v1/hosts/<host_id>/support
        Sends a request to the host agent on the specified host to generate and
        return a support bundle to the deployment unit. The request is
        asynchronous and not guaranteed to succeed.
        Returns a 404 error code if the specified host does not exist.
        :param str host_id: ID of the host
        """
        if not _provider.get_host(host_id):
            log.error('Unable to request support bundle. No matching host found: %s',
                      host_id)
            abort(404)
        try:
            _provider.request_support_bundle(host_id)
        except (SupportRequestFailed, BBMasterNotFound):
            log.exception("Request to generate support bundle failed.")
            abort(503)


class HostSupportCommandController(RestController):

    @enforce(required=['admin'])
    @expose('json')
    def post(self, host_id):
        """
        Handles requests of type POST /v1/hosts/<host_id>/support
        Sends a request to the host agent on the specified host to generate and
        return a support bundle to the deployment unit. The request is
        asynchronous and not guaranteed to succeed.
        Returns a 404 error code if the specified host does not exist.
        :param str host_id: ID of the host
        """
        if not _provider.get_host(host_id):
            log.error('Unable to request support command. No matching host found: %s',
                      host_id)
            abort(404)
        if hasattr(pecan.core.state, "request") and hasattr(pecan.core.state.request, "json_body"):
            msg_body = pecan.core.state.request.json_body
        else:
            log.error('Unable to request support command. Invalid json body.')
            abort(400)
        try:
            _provider.run_support_command(host_id, msg_body)
        except (SupportCommandRequestFailed, BBMasterNotFound):
            log.exception("Request to run support command failed.")
            abort(503)

class HostSupportController(RestController):
    """Controller for hosts' support related requests"""
    bundle = HostSupportBundleController()
    command = HostSupportCommandController()

class HostsController(RestController):
    """ Controller for hosts related requests"""
    roles = HostRolesController()
    support = HostSupportController()

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

    @enforce(required=['admin'])
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
        except RoleUpdateConflict as e:
            log.exception('Host %s removal failed', host_id)
            return _json_error_response(pecan.response, 409, e)
        except DuConfigError as e:
            log.exception('Host %s removal failed', host_id)
            return _json_error_response(pecan.response, 400, e)

class ServicesController(RestController):
    @enforce(required=['admin'])
    @expose('json')
    def get_one(self, service_name):
        log.debug('Getting details for service %s', service_name)
        out = _provider.get_service_settings(service_name)
        if not out:
            # Service doesn't exist
            log.error('No matching service found for %s', service_name)
            abort(404)
        return out['settings']

    @enforce(required=['admin'])
    @expose('json')
    def put(self, service_name):
        msg_body = pecan.request.body
        if len(msg_body) == 0:
            msg_body = {}
        else:
            try:
                msg_body = pecan.request.json_body
            except Exception as e:
                abort(400, str(e))

        if not isinstance(msg_body, dict):
            abort(400, 'Invalid JSON body')

        log.debug('Setting service %s with settings %s', service_name, msg_body)
        try:
            _provider.set_service_settings(service_name, msg_body)
        except ServiceNotFound:
            log.exception('Service %s is not found', service_name)
            abort(404)
        except ServiceConfigFailed:
            # Running the service config script failed
            log.exception('Setting service config failed')
            abort(500)
