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
import collections
import six
from pecan import abort, expose
from pecan.rest import RestController
from resmgr.controllers.enforce_policy import enforce
from resmgr.exceptions import *
from six import itervalues

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
    try:
        response.json = {'message': '%s: %s' % (exc.__class__.__name__, exc.msg)}
    except Exception:
        response.json = {'message': 'Request Failed'}
    return response

def _validate_incoming_request_body(req_body):
    """Validate incoming request body for expected structure"""
    if len(req_body) == 0:
        req_body = {}
    else:
        try:
            req_body = pecan.request.json_body
        except Exception as e:
            raise MalformedRequest(400, str(e))

    if not isinstance(req_body, dict):
        raise MalformedRequest(400, 'Invalid JSON body')

    return req_body

def _convert_json_unicode_to_str(data):
    """ Converts an incoming dict with unicode to string"""
    if isinstance(data, basestring):
        return str(data)
    elif isinstance(data, collections.Mapping):
        return dict(map(_convert_json_unicode_to_str, data.iteritems()))
    elif isinstance(data, collections.Iterable):
        return type(data)(map(_convert_json_unicode_to_str, data))
    else:
        return data

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
        Handles request of type GET /<v1/v2>/roles
        :return: a list of available roles
        :rtype: list
        """
        log.debug('Getting all roles')
        out = _provider.get_all_roles()

        if not out:
            log.info('No roles present')
            return []

        return [val for val in itervalues(out)]

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

    @enforce(required=['admin'])
    @expose('json')
    def post(self):
        """
        Handles request of type POST /<v1/v2>/roles
        """
        msg_body = {}
        try:
            msg_body = _validate_incoming_request_body(pecan.request.body)
            if six.PY2:
                # Pecan reads incoming payload in unicode format.
                # Convert the json contents from unicode to string.
                # This issue is only seen in py2 environment.
                msg_body = _convert_json_unicode_to_str(msg_body)
        except MalformedRequest as e:
            log.exception('Bad request body', e)
            abort(e.errorCode, e.errorMsg)

        log.debug('Creating a new role with message body %s.', msg_body)
        try:
            _provider.create_role(msg_body)
        except RoleKeyMalformed as e:
            log.error('Role not created due to invalid payload: %s', e)
            return _json_error_response(pecan.response, 400, e)
        except RoleVersionExists as e:
            log.error('Role already exists: %s', e)
            return _json_error_response(pecan.response, 409, e)
        except Exception as e:
            log.exception('Role not created: %s', e)
            return _json_error_response(pecan.response, 400, e)

class RolesControllerV2(RolesController):

    @expose('json')
    def get_one(self, name, version='active'):
        """
        Handles request of type GET /v2/roles/<role_name>/?version="version_name"
        :param str name: Name of the role
        :return: dictionary of properties for the role
        :rtype: dict
        """
        try:
            version = version.lower()
            log.debug('Getting details for role %s with version %s',
                      name, version)
            out = _provider.get_role_with_version(name, version)
            return out[name]
        except RoleVersionNotFound as e:
            log.error('No matching role found for %s with version %s',
                       name, version)
            return _json_error_response(pecan.response, 404, e)
        except Exception as e:
            log.error('Failed to get details for role %s with version %s',
                      name, version)
            return _json_error_response(pecan.response, 400, e)

    @enforce(required=['admin'])
    @expose('json')
    def put(self, name, version, active):
        """
        Handles request of type
        PUT /v2/roles/<role_name>/?version="version_name"&active=True
        :param str name: Name of the role
        :param str version: Role version
        :param boolean active: Flag to indicate if role is to be
                                    marked as an active role
        """
        try:
            log.debug('Marking role %s with version %s as active',
                      name, version)
            out = _provider.mark_role_version_active(name, version, active)
        except RoleVersionNotFound as e:
            log.error('No matching role found for %s with version %s',
                       name, version)
            return _json_error_response(pecan.response, 404, e)
        except RoleInactiveNotAllowed as e:
            log.error('Role %s with version %s cannot be marked as inactive via API.',
                      name, version)
            return _json_error_response(pecan.response, 400, e)
        except Exception as e:
            log.error('Failed to mark role %s with version %s as active',
                      name, version)
            return _json_error_response(pecan.response, 400, e)

class HostRolesVersionController(RestController):

    @enforce(required=['admin'])
    @expose('json')
    def put(self, host_id, role_name, version):
        """
        Handles requests of type PUT /v1/hosts/<host_id>/roles/<role_name>/versions/<version>
        Assigns the specific version of specified role to the host.
        The body must either be empty or a Json dictionary.
        :param str host_id: ID of the host
        :param str role_name: Name of the role being assigned
        :param str version: Version of the role to assign
        """
        msg_body = {}
        try:
            msg_body = _validate_incoming_request_body(pecan.request.body)
        except MalformedRequest as e:
            log.exception('Bad request body', e)
            abort(e.errorCode, e.errorMsg)

        log.debug('Assigning role %s, version %s to host %s with message body %s',
                  role_name, version, host_id, msg_body)
        try:
            _provider.add_role(host_id, role_name, version, msg_body)
        except (RoleNotFound, HostNotFound, HostDown) as e:
            log.exception('Role %s or Host %s not found: %s', role_name,
                          host_id, e)
            return _json_error_response(pecan.response, 404, e)
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

class HostRolesController(RestController):
    """Controller for hosts' roles related requests"""

    versions = HostRolesVersionController()

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
        msg_body = {}
        try:
            msg_body = _validate_incoming_request_body(pecan.request.body)
        except MalformedRequest as e:
            log.exception('Bad request body', e)
            abort(e.errorCode, e.errorMsg)

        log.debug('Assigning role %s to host %s with message body %s',
                  role_name, host_id, msg_body)
        try:
            _provider.add_role(host_id, role_name, None, msg_body)
        except (RoleNotFound, HostNotFound, HostDown) as e:
            log.exception('Role %s or Host %s not found: %s', role_name,
                          host_id, e)
            return _json_error_response(pecan.response, 404, e)
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

        msg_body = {}
        if hasattr(pecan.core.state, "request") and hasattr(pecan.core.state.request, "json_body"):
            msg_body = pecan.core.state.request.json_body

        try:
            _provider.request_support_bundle(host_id, msg_body)
        except (SupportRequestFailed, SideKickNotFound):
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

class HostCertController(RestController):
    """Controller for hosts' certs related requests"""
    @enforce(required=['admin'])
    @expose('json')
    def put(self,host_id):
        """
        Handles requests of type PUT /v1/hosts/<host_id>/certs
        Sends a request to the host agent on the specified host to refresh the
        host certificates.
        Returns a 404 error code if the specified host does not exist.
        :param str host_id: ID of the host
        """
        if not _provider.get_host(host_id):
            log.error('Unable to request host certificate refresh. No matching '\
                'host found: {}'.format(host_id))
            abort(404)
        try:
            _provider.request_cert_refresh(host_id)
        except (CertRefreshRequestFailed, BBMasterNotFound):
            log.exception("Request to refresh host certificate failed.")
            abort(503)

    @enforce(required=['admin'])
    @expose('json')
    def get(self, host_id):
        """
        Handles requests of type GET /v1/hosts/<host_id>/certs
        Gets the details about certificate info for the specified host.

        Returns a 404 error code if the specified host does not exist.
        :param str host_id: ID of the host
        """
        try:
            host_cert_info =  _provider.get_cert_info(host_id)
            return host_cert_info
        except HostNotFound:
            log.error('Unable to fetch certificate information for the host.'\
                ' No matching host found: {}'.format(host_id))
            abort(404)

class HostSupportController(RestController):
    """Controller for hosts' support related requests"""
    bundle = HostSupportBundleController()
    command = HostSupportCommandController()

class HostsController(RestController):
    """ Controller for hosts related requests"""
    roles = HostRolesController()
    support = HostSupportController()
    certs = HostCertController()

    @expose('json')
    def get_all(self):
        """
        Handles requests of type GET /v1/hosts. Returns all hosts known
        to the resource manager.
        :return: list of hosts. Empty list if no hosts are present.
        :rtype: list
        """
        log.debug('Getting details for all hosts')
        res = _provider.get_all_hosts(**{'role_settings': None})

        if not res:
            log.info('No hosts present')
            return []

        return [val for val in itervalues(res)]

    @expose('json')
    def get_one(self, host_id):
        """
        Handles requests of type GET /<v1/v2>/hosts/<id>
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
        Handles requests of type DELETE /<v1/v2>/hosts/<id>
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

class HostsControllerV2(HostsController):

    @expose('json')
    def get_all(self, **kwargs):
        """
        Handles requests of type GET /v2/hosts. Returns all hosts known
        to the resource manager.
        :return: list of hosts. Empty list if no hosts are present.
        :rtype: list
        """
        log.debug('Getting details for all hosts')
        # Currently this API is experimental and subject to change if more
        # filters, flags and pagination need to be added. Till that is
        # formalized perform a "static" validation of parameters being passed.
        valid_keys = ['role_settings']
        valid_values = ['true', 'false']
        params = {}
        for key, val in kwargs.items():
            if key not in valid_keys:
                pecan.abort(400, 'Invalid flag {}'.format(key))
            elif val.lower() not in valid_values:
                pecan.abort(400, 'Malformed request')
            params[key] = val.lower() == 'true'

        res = _provider.get_all_hosts(**params)

        if not res:
            log.info('No hosts present')
            return []

        return [val for val in itervalues(res)]

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
