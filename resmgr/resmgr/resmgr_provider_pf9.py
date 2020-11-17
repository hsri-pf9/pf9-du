# Copyright 2018 Platform9 Systems Inc.
# All Rights Reserved

__author__ = 'Platform9'

# pylint: disable=no-self-use, bare-except, too-many-function-args
# pylint: disable=redefined-builtin, too-many-branches, wildcard-import
# pylint: disable=too-many-locals, too-many-instance-attributes
# pylint: disable=too-many-statements, unused-wildcard-import
# pylint: disable=no-member

"""
This module provides real implementation of Resource Manager provider interface
"""

import datetime
import imp
import logging
import notifier
import json
import os
import threading
import rabbit
import random
import requests
import string
import subprocess
import tempfile

from six.moves.urllib.parse import urlparse
from six.moves.configparser import ConfigParser
from six import iteritems
from six import iterkeys
from bbcommon.utils import is_satisfied_by
from six.moves.queue import Queue, Empty
from resmgr import role_states, dict_subst
from resmgr.dbutils import ResMgrDB
from resmgr.exceptions import *
from resmgr.resmgr_provider import ResMgrProvider
from resmgr.consul_roles import ConsulRoles, ConsulUnavailable
from prometheus_client import Gauge

log = logging.getLogger(__name__)

TIMEDRIFT_MSG_LEVEL = 'warn'
TIMEDRIFT_MSG = 'Host clock may be out of sync'

# Maintain some state for resource manager

# FIXME: get rid of this - everything should be in the database
_unauthorized_hosts = {}
_unauthorized_host_status_time = {}
_unauthorized_host_status_time_on_du = {}
_authorized_host_role_status = {}
_hosts_hypervisor_info = {}
_hosts_extension_data = {}
_hosts_message_data = {}
_hosts_cert_data = {}
_host_lock = threading.Lock()
_role_update_lock = threading.RLock()

# Prometheus metrics for host information.
g_host_up = Gauge('resmgr_host_up', "Is host responding?", ['host_id', 'host_name'])
g_host_converged = Gauge("resmgr_host_role_converged", "Resmgr host role converged",
                         ['host_id', 'host_name'])
g_host_has_pmk_role = Gauge("resmgr_host_is_pmk_host", "Is PMK host?",
                            ['host_id', 'host_name'])
g_host_cert_expiry_date_ts = Gauge('resmgr_host_cert_expiry_date',
                                   'Host cert expiry date (timestamp)',
                                   ['host_id', 'host_name'])
g_host_cert_start_date_ts = Gauge('resmgr_host_cert_start_date',
                                  'Host cert start date (timestamp)',
                                  ['host_id', 'host_name'])

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
            log.error('GET call on %s failed with return code %d', url, r.status_code)
            raise BBMasterNotFound('Return code: %s' % str(r.status_code))
        return r.json()

    except requests.exceptions.RequestException as e:
        log.error('GET call on %s failed', url)
        raise BBMasterNotFound(e)

def _record_host_cert_expiry_date_metrics(end_date, host_id, host_name):
    g_host_cert_expiry_date_ts.labels(host_id, host_name).set(end_date)

def _remove_host_cert_expiry_date_metrics(host_id, host_name):
    try:
        g_host_cert_expiry_date_ts.remove(host_id, host_name)
    except KeyError:
        log.exception('KeyError exception encountered while removing'\
                 ' host_cert_expiry_date_ts guage for hostid: %s hostname: %s',
                 host_id, host_name)
    except Exception as e:
        log.exception('Generic exception encountered while removing'\
                      ' host_cert_expiry_date_ts guage for hostid: {}'\
                      ' hostname: {}, Exception details: {}'.format(host_id,
                       host_name, e))

def _record_host_cert_start_date_metrics(start_date, host_id, host_name):
    g_host_cert_start_date_ts.labels(host_id, host_name).set(start_date)

def _remove_host_cert_start_date_metrics(host_id, host_name):
    try:
        g_host_cert_start_date_ts.remove(host_id, host_name)
    except KeyError:
        log.exception('KeyError exception encountered while removing'\
                 ' host_cert_start_date_ts guage for hostid: %s hostname: %s',
                 host_id, host_name)
    except Exception as e:
        log.exception('Generic exception encountered while removing'\
                      ' g_host_cert_start_date_ts guage for hostid: {}'\
                      ' hostname: {}, Exception details: {}'.format(host_id,
                       host_name, e))

def _record_host_cert_metrics(host_cert_info, host_id, host_name):
    try:
        status = host_cert_info['details']['status']
        expiry_date = host_cert_info['details']['expiry_date']
        start_date = host_cert_info['details']['start_date']

        if status == 'successful':
            _record_host_cert_expiry_date_metrics(expiry_date,host_id, host_name)
            _record_host_cert_start_date_metrics(start_date, host_id, host_name)
        elif status == 'failed':
            log.error('Certificate query on hostid: {} hostname {} has '\
                'failed.'.format(host_id, host_name))
        else:
            log.debug('Certificate query on hostid: {} hostname {} is {}'.format(
                host_id, host_name, status))
    except KeyError:
        log.exception('KeyError exception while getting cert details for host '\
            'id: {} host name: {}'.format(host_id, host_name))
    except Exception:
        log.exception('Generic exception while getting cert details for host '\
            'id: {} host name: {}'.format(host_id, host_name))


def _remove_all_host_cert_metrics(host_id, host_name):
    _remove_host_cert_expiry_date_metrics(host_id, host_name)
    _remove_host_cert_start_date_metrics(host_id, host_name)

def _record_host_up_metric(responding_state, host_id, host_name):
    g_host_up.labels(host_id, host_name).set(responding_state)

def _remove_host_up_metric(host_id, host_name):
    try:
        g_host_up.remove(host_id, host_name)
    except KeyError:
        log.info('KeyError exception encountered while removing'\
                 ' host_up guage for hostid: %s hostname: %s',
                 host_id, host_name)
    except Exception as e:
        log.exception('Generic exception encountered while removing'\
                      ' host_up guage for hostid: {} hostname: {}, ' \
                      ' Exception details: {}'.format(host_id, host_name, e))

def _record_host_converged_metric(converged_state, host_id, host_name):
    g_host_converged.labels(host_id, host_name).set(converged_state)

def _remove_host_converged_metric(host_id, host_name):
    try:
        g_host_converged.remove(host_id, host_name)
    except KeyError:
        log.info('KeyError exception encountered while removing'\
                 ' host_converged guage for hostid: %s hostname: %s',
                 host_id, host_name)
    except Exception as e:
        log.exception('Generic exception encountered while removing'\
                      ' host_converged guage for hostid: {} hostname: {}, ' \
                      ' Exception details: {}'.format(host_id, host_name, e))

def _record_host_has_pmk_role_metric(has_pmk, host_id, host_name):
    g_host_has_pmk_role.labels(host_id, host_name).set(has_pmk)

def _remove_host_has_pmk_role_metric(host_id, host_name):
    try:
        g_host_has_pmk_role.remove(host_id, host_name)
    except KeyError:
        log.info('KeyError exception encountered while removing'\
                 ' pmk_role guage for hostid: %s hostname: %s',
                 host_id, host_name)
    except Exception as e:
        log.exception('Generic exception encountered while removing'\
                      ' pmk_role guage for hostid: {} hostname: {}, ' \
                      ' Exception details: {}'.format(host_id, host_name, e))

def _remove_all_host_metrics(host_id, host_name):
    _remove_host_up_metric(host_id, host_name)
    _remove_host_converged_metric(host_id, host_name)
    _remove_host_has_pmk_role_metric(host_id, host_name)
    _remove_all_host_cert_metrics(host_id, host_name)

def _update_custom_role_settings(app_info, role_settings, roles):
    """
    :param app_info: The app configuration returned from
                     ResMgrDB.query_host_details()[host_id]['roles_config']
    :type dict:
    :param role_settings: Contains info that specifies custom role settings
                          From the DB. Updated on the call to add_role.
    :type dict:
    :param roles: Active roles in the database
    """
    new_roles = dict((role.rolename, role.customizable_settings) for role in roles)

    # Iterate over all apps in app_info
    for given_app_name in iterkeys(app_info):
        for role_name, settings in iteritems(new_roles):
            # Role is considered only if it is part of the provided role_settings
            # AND part of the app name
            if role_name not in role_settings:
                continue
            # TODO: We should really have a better way of making this association between app and role
            if given_app_name not in role_name:
                continue

            for setting_name, setting in iteritems(settings):
                path = setting['path'].split('/')
                # Traverse the config according to the path of the default setting.
                # Then, insert the custom role setting into the app info
                app_info_temp = app_info[given_app_name]
                for key in path:
                    app_info_temp = app_info_temp[key]
                if setting_name in role_settings[role_name]:
                    app_info_temp[setting_name] = role_settings[role_name][setting_name]
                else:
                    app_info_temp[setting_name] = ''


def _load_role_confd_files(role_metadata_location, config):
    confd = os.path.join(role_metadata_location, 'conf.d')
    if not os.path.isdir(confd):
        log.warning('Role configuration directory %s does not exist. Not '
                    'loading role confd files.', confd)
        return

    conf_files = [os.path.join(confd, f)
                  for f in os.listdir(confd)
                  if f.endswith('.conf')]
    for conf_file in conf_files:
        try:
            config.read(conf_file)
            log.info('Read role config %s', conf_file)
        except ConfigParser.Error:
            log.exception('Failed to parse config file %s.', conf_file)

def _run_script(cmd):
    try:
        subprocess.check_call(cmd)
    except:
        log.exception('Failed running %s', cmd)
        raise

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
        rabbit_username = config.get('amqp', 'username')
        rabbit_password = config.get('amqp', 'password')
        self.rabbit_mgmt_cl = rabbit.RabbitMgmtClient(rabbit_username,
                                                      rabbit_password)

        # Map to keep track of when the last push was made to each host.
        # This will be updated each time we push configuration to a host,
        # and checked when we process the host. Without this, when a host
        # is reported as 'ok' by bbmaster, it's not clear whether it's
        # converged or it just hasn't started working on the new config yet.
        self._last_config_push_time = {}

    def get_all_roles(self):
        """
        Returns information of all active roles
        :rtype: dict
        """
        query_op = self.db_handler.query_roles()
        result = {}
        for role in query_op:
            default_settings = dict((setting_name, setting['default'])
                                    for (setting_name, setting)
                                    in iteritems(role.customizable_settings))
            role_attrs = {
                'name': role.rolename,
                'display_name': role.displayname,
                'description': role.description,
                'active_version': role.version,
                'default_settings': default_settings
            }
            result[role.rolename] = role_attrs

        return result

    def get_role(self, role_name):
        """
        Get public portion of roles information for an active role
        :param str role_name: Name of the role
        :return: Dictionary of the role attributes
        :rtype: dict
        """
        role = self.db_handler.query_role(role_name)
        if role:
            default_settings = dict((setting_name, setting['default'])
                                    for (setting_name, setting)
                                    in iteritems(role.customizable_settings))
            result = {
                role.rolename: {
                    'name': role.rolename,
                    'display_name': role.displayname,
                    'description': role.description,
                    'active_version': role.version,
                    'default_settings': default_settings
                }
            }
        else:
            result = None

        return result

    def get_role_with_version(self, role_name, version):
        """
        Returns public portion of all information
        about a role with given version
        :param str role_name: Name of the role
        :param str version: Version of the role
        :return: dictionary of the role information
        :rtype: dict
        """
        if version == "active":
            role = self.db_handler.query_role(role_name)
        else:
            role = self.db_handler.query_role_with_version(role_name, version)

        if role:
            default_settings = dict((setting_name, setting['default'])
                                    for (setting_name, setting)
                                    in iteritems(role.customizable_settings))
            result = {
                role.rolename: {
                    'name': role.rolename,
                    'display_name': role.displayname,
                    'description': role.description,
                    'role_version': role.version,
                    'default_settings': default_settings
                }
            }
        else:
            raise RoleVersionNotFound(role_name, version)

        return result

    def mark_role_version_active(self, role_name, version, active):
        """
        Marks a role with given version as active
        :param role_name: Name of the role
        :param version: version of the role
        :param active: Flag indicating if the role is to marked as active.
        """
        if not active.lower() == 'true':
            raise RoleInactiveNotAllowed("Role %s version %s"\
                                         % (role_name, version))

        log.debug('Marking role %s with version %s as active',
                  role_name, version)
        self.db_handler.mark_role_active(role_name, version)

    def create_role(self, role_info):
        """
        Creates a role with incoming role information and stores
        this role in the database.
        :param role_info : JSON with role information.
        """
        role_keys = {
            'role_name': str,
            'role_version': str,
            'display_name': str,
            'description': str,
            'customizable_settings': dict,
            'rabbit_permissions': dict,
            'config': dict,
            }
        for key in role_keys:
            if key not in role_info.keys() or not \
               isinstance(role_info[key], role_keys[key]):
                log.error('Malformed/Missing role key: %s, type %s',
                          key, role_keys[key])
                raise RoleKeyMalformed("Malformed/Missing role key %s" % key)

        if 'active' in role_info and not \
           isinstance(role_info['active'], bool):
            log.error('Malformed role key: %s, type %s, actual type %s',
                      'active', bool, type(role_info['active']))
            raise RoleKeyMalformed("Malformed role active key")

        role_name = role_info['role_name']
        role_version = role_info['role_version']

        # Check if the role with role_version already exists.
        role = self.db_handler.query_role_with_version(role_name, role_version)
        if role:
            log.error('Role %s with version %s already exists',
                      role_name, role_version)
            raise RoleVersionExists("Role %s with version %s already exists"\
                                     % (role_name, role_version))

        log.info('Creating role with rolename %s, role_version %s',
                  role_name, role_version)
        # Currently, save_role_in_db treats every incoming role that needs to
        # be saved in DB as an active role. Rest of the roles present with the
        # same role name, but different version are marked as not-active.
        self.db_handler.save_role_in_db(role_name, role_version, role_info)
        log.debug('Created role with rolename %s, role_version %s',
                  role_name, role_version)

    def get_app_versions(self, role_name):
        role = self.db_handler.query_role(role_name)
        if role:
            return dict((app, config['version'])
                        for (app, config)
                        in iteritems(role.desiredconfig))
        return None

    def active_role_config(self):
        """
        Get the details of all roles that are marked as active
        :return: Dictionary of role attributes
        :rtype: dict
        """
        log.info('Building active role cache')
        query_op = self.db_handler.query_roles()
        result = {}
        for role in query_op:
            result[role.rolename] = {
                'role_id': role.id,
                'config': role.desiredconfig
            }

        return result

    def _filter_host_configuration(self, app_info):
        """
        Filter out the app configuration that is not needed
        by the host.
        """
        for _, app_spec in iteritems(app_info):
            if 'du_config' in app_spec:
                del app_spec['du_config']

    def push_configuration(self, host_id, app_info):
        """
        Push app configuration to backbone service
        :param str host_id: host identifier
        :param dict app_info: app information that needs to be set in the configuration
        :raises HostConfigFailed: if setting the configuration fails or times out
        :raises BBMasterNotFound: if communication to the backbone fails
        """
        self._filter_host_configuration(app_info)
        log.info('Applying configuration %s to %s', app_info, host_id)
        url = "%s/v1/hosts/%s/apps" % (self.bb_url, host_id)
        try:
            r = requests.put(url, json.dumps(app_info))

            if r.status_code != requests.codes.ok:
                log.error('PUT request failed, response status code %d', r.status_code)
                raise HostConfigFailed('Error in PUT request response: %d' % r.status_code)

            # when we process the host, we need to know if the update we get
            # from hostagent was received since the last push.
            self._last_config_push_time[host_id] = datetime.datetime.utcnow()

        except requests.exceptions.RequestException as exc:
            log.error('Configuring host %s failed: %s', host_id, exc)
            raise BBMasterNotFound(exc)

    def received_since_last_push(self, host_id, host_info):
        """
        Check a host_info update from bbmaster to see if it's been received
        since the last time a new config was pushed to the host. Use this
        to decide whether a host_status should trigger or state change after
        a push, or ignore it if it's leftover in the bbmaster.
        """
        update_time_string = host_info.get('timestamp_on_du', None)
        if not update_time_string:
            log.warn('hostagent update for host %s doesn\'t contain '
                     'timestamp_on_du!', host_id)
            return True
        try:
            # this format must match the one in bbone_provider_pf9_pika,
            # consume_msg
            update_time = datetime.datetime.strptime(update_time_string,
                                                     "%Y-%m-%d %H:%M:%S.%f")
            return update_time > self._last_config_push_time[host_id]
        except ValueError:
            log.error('update time in host_info \'%s\' for host %s is in the '
                      'wrong format!', update_time_string, host_id)
            return True
        except KeyError:
            # host_id isn't there, no push yet
            return True

    @staticmethod
    def get_current_app_config(host_details, include_deauthed_roles=False):
        """
        Calculate the current app config, either to be pushed to a host,
        or to be used with an auth event.
        :param host_details: the full host data
        :param include_deauthed_roles: If true, includes config for roles
            that are in the process of being removed. Useful when running
            deauth events that need config for apps that are being removed.
        :returns: dict something this (test-role is an 'app' name) {
        "test-role": {
            "version": "1.0",
            "service_states": {"test-service": "true"},
            "config": {
                "test_conf": {
                    "DEFAULT": {
                        "conf1": "conf1_value"
                    },
                    "customizable_section": {
                        "customizable_key": "default value for customizable_key"
                    }
                }
            }
        }}
        """
        app_info = host_details['apps_config_including_deauthed_roles'] if \
            include_deauthed_roles else host_details['apps_config']
        role_settings = host_details['role_settings']
        roles = host_details['role_details']
        _update_custom_role_settings(app_info, role_settings, roles)
        return app_info

    def move_to_preauth_state(self, host_id, host_details,
                              rolename, current_state):
        """
        Run the on_auth role event handler.
        on success move to the PRE_AUTH state
        on failure move back to NOT_APPLIED.
        """
        app_info = self.get_current_app_config(host_details)
        if current_state == role_states.START_APPLY:
            with self.db_handler.move_new_state(host_id, rolename,
                                                role_states.START_APPLY,
                                                role_states.PRE_AUTH,
                                                role_states.NOT_APPLIED):
                self.on_auth(rolename, app_info)
        elif current_state == role_states.START_EDIT:
            with self.db_handler.move_new_state(host_id, rolename,
                                                role_states.START_EDIT,
                                                role_states.PRE_AUTH,
                                                role_states.APPLIED):
                self.on_auth(rolename, app_info)
        else:
            raise DuConfigError('Unexpected state %s when trying to move to '
                                'preauth' % current_state)

    def move_to_auth_converging_state(self, host_id, host_details, rolename):
        with self.db_handler.move_new_state(host_id, rolename,
                                            role_states.PRE_AUTH,
                                            role_states.AUTH_CONVERGING,
                                            role_states.PRE_AUTH):
            app_info = self.get_current_app_config(host_details)
            log.info('Sending request to backbone to add role %s to %s with '
                     'config %s', rolename, host_id, app_info)
            self.push_configuration(host_id, app_info)

    def move_to_pre_deauth_state(self, host_id, host_details,
                                 rolename, current_state):
        with self.db_handler.move_new_state(host_id, rolename,
                                            current_state,
                                            role_states.PRE_DEAUTH,
                                            role_states.APPLIED):
            app_info = self.get_current_app_config(host_details,
                                                   include_deauthed_roles=True)
            self.on_deauth(rolename, app_info)

    def move_to_deauth_converging_state(self, host_id, host_details, rolename):
        with self.db_handler.move_new_state(host_id, rolename,
                                            role_states.PRE_DEAUTH,
                                            role_states.DEAUTH_CONVERGING,
                                            role_states.PRE_DEAUTH):
            log.debug('Sending request to backbone to remove role %s from %s',
                      rolename, host_id)
            credentials = self.db_handler.query_rabbit_credentials(
                                    host_id=host_id,
                                    rolename=rolename)
            if credentials:
                self._delete_rabbit_credentials(credentials)

            app_info = self.get_current_app_config(host_details)
            self.push_configuration(host_id, app_info)

    def move_to_applied_state(self, host_id, host_details, rolename):
        with self.db_handler.move_new_state(host_id, rolename,
                                            role_states.AUTH_CONVERGED,
                                            role_states.APPLIED,
                                            role_states.AUTH_ERROR):
            log.info('Running on_auth_converged_event')
            app_info = self.get_current_app_config(host_details,
                                include_deauthed_roles=True)
            self.on_auth_converged(rolename, app_info)

    def move_to_not_applied_state(self, host_id, host_details, rolename):
        """
        Note there's no role transition to 'NOT_APPLIED' because the
        the role is removed from the associations.
        """
        try:
            log.info('Running on_deauth_converged_event for %s(%s)',
                     host_id, rolename)
            app_info = self.get_current_app_config(host_details,
                                include_deauthed_roles=True)
            self.on_deauth_converged(rolename, app_info)

            # now we can drop the association and remove from the host
            self.db_handler.remove_role_from_host(host_id, rolename)
            if not self.db_handler.get_all_role_associations(host_id):
                # There is a chance that we are trying to delete a host when
                # the host is offline. Remove the metrics entries too since
                # the host will not become an unauthorized host prior to being
                # removed.
                _remove_all_host_metrics(host_id, host_details['hostname'])
                self.db_handler.delete_host(host_id)
        except Exception as e:
            log.error('Failed to remove role %s from host %s: %s',
                      rolename, host_id, e)
            self.db_handler.advance_role_state(host_id, rolename,
                                               role_states.DEAUTH_CONVERGED,
                                               role_states.DEAUTH_ERROR)

    def on_auth(self, role_name, app_config):
        self._run_event('on_auth', role_name, app_config)

    def on_deauth(self, role_name, app_config):
        self._run_event('on_deauth', role_name, app_config)

    def on_auth_converged(self, role_name, app_config):
        self._run_event('on_auth_converged', role_name, app_config)

    def on_deauth_converged(self, role_name, app_config):
        self._run_event('on_deauth_converged', role_name, app_config)

    def _run_event(self, event_method, role_name, app_config):
        """
        A useful app_config dict looks like:
        'rolename': {
          'du_config': {
            'auth_events': {
              'type': 'python',
              'module_path': '/path/to/events.py'
              'params' {
                'kwarg1': 'val1',
                'kwarg2': 'val2'
              }
            }
          }
          ...
        }
        """
        # Dive into the app_config dictionary to find the auth_events
        # spec. Do nothing if it (or any of the intermediate keys)
        # is missing.

        # Fetch the version from the default app for a given role.
        # This is required as role_name is not always same as the app name.
        # Example: role_name might be pf9-ostackhost-neutron, whereas
        #          the app_name is pf9-ostackhost
        default_role = self.db_handler.query_role(role_name)
        default_app_name_list = set(default_role.desiredconfig.keys())
        default_app_name = next(iter(default_app_name_list))
        log.debug("Found default_app_name %s", default_app_name)
        version = app_config[default_app_name]['version']

        # Once the version is available, fetch the role and populate
        # the role map from the role information.
        role = self.db_handler.query_role_with_version(role_name, version)
        role_apps = set(role.desiredconfig.keys())
        log.debug("Found role_apps %s for version %s", role_apps, version)

        for app_name, app_details in iteritems(app_config):
            if app_name not in role_apps or \
               'du_config' not in app_details or \
               'auth_events' not in app_details['du_config']:
                continue

            event_spec = app_details['du_config']['auth_events']

            # add the host configuration to the du_config events if needed
            host_config = app_config.get(app_name, {}).get('config', {})
            event_spec = dict_subst.substitute(event_spec,
                    {'__HOST_CONFIG__': host_config})
            events_type = event_spec.get('type', None)
            if events_type == 'python':
                self._run_python_event(event_method, event_spec)
            else:
                log.warn('Unknown auth_events type \'%s\'.', events_type)

    def _run_python_event(self, event_method, event_spec):
        """
        Run a method from the python module whose path is in event_spec. Will
        only raise DuConfigError.
        """
        log.debug('_run_python_event with event method: %s', event_method)
        module_path = event_spec.get('module_path', None)
        if not module_path:
            log.warn('No auth events module_path specified in app_config.')
        elif module_path.startswith('http://') or \
             module_path.startswith('https://'):
            url = module_path
            module_path = self._fetch_event_module(url)
            log.info('Downloaded event module %s to %s', url, module_path)
        elif not os.path.isfile(module_path):
            log.warn('Auth events module %s not found, not running event '
                     '%s.', module_path, event_method)
        else:
            params = event_spec.get('params', {})
            try:
                module_name = os.path.splitext(
                        os.path.basename(module_path))[0]
                module = imp.load_source(module_name, module_path)
                log.debug('about to invoke method %s of module %s',
                         event_method, module_path)
                if hasattr(module, event_method):
                    method = getattr(module, event_method)
                    # Pass resmgr logger object to auth_event handler method
                    method(logger=log, **params)
                    log.info('Auth event \'%s\' method from %s ran successfully',
                             event_method, module_path)
                else:
                    log.info('No handler for %s in %s', event_method,
                             module_path)
            except Exception as e:
                reason = 'Auth event \'%s\' method failed to run from %s: %s' \
                         % (event_method, module_path, e)
                log.exception(reason)
                raise DuConfigError(reason)

    @staticmethod
    def _fetch_event_module(url):
        """
        Download a module, save it in a temporary file, and return the path.
        FIXME: improvements:
        + checksums
        + cache
        """
        parsed = urlparse.urlparse(url)
        basename = parsed.path.basename()
        resp = requests.get(url)
        resp.raise_for_status()

        with tempfile.NamedTemporaryFile(prefix=basename, delete=False) as f:
            f.write(resp.body)
            return f.name

    def _delete_rabbit_credentials(self, credentials):
        for credential in credentials:
            try:
                self.rabbit_mgmt_cl.delete_user(credential.userid)
            except:
                log.error('Failed to clean up RabbitMQ user: %s',
                          credential.userid)

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

    def get_all_hosts(self, role_settings=False):
        """
        Returns information about all known hosts.
        :param role_settings: Boolean indicating whether role settings need to
                              be returned in the response dict
        :rtype: dict:
        """
        result = {}
        query_op = self.db_handler.query_hosts()
        for host in query_op:
            host_id = host['id']
            if _authorized_host_role_status.get(host_id):
                host['role_status'] = _authorized_host_role_status[host_id]
            if role_settings is not None:
                # /v1/hosts sends role_settings as None.
                host['role_settings'] = {}
            if role_settings:
                host['role_settings'] = \
                    self.db_handler.get_all_custom_settings(host_id)
            host['hypervisor_info'] = _hosts_hypervisor_info.get(host_id, '')
            host['extensions'] = _hosts_extension_data.get(host_id, '')
            host['cert_info'] = _hosts_cert_data.get(host_id, '')
            host['message'] = _hosts_message_data.get(host_id, '')
            result[host_id] = host

        # Add unauthorized hosts into the result
        log.debug('Looking up unauthorized hosts')
        iaas_9086_hosts = []
        with _host_lock:
            for id in iterkeys(_unauthorized_hosts):
                if id in result:
                    iaas_9086_hosts.append(id)
                    continue
                host = _unauthorized_hosts[id]
                host['hypervisor_info'] = _hosts_hypervisor_info.get(host['id'], '')
                host['extensions'] = _hosts_extension_data.get(host['id'], '')
                host['cert_info'] = _hosts_cert_data.get(host['id'], '')
                host['message'] = _hosts_message_data.get(host['id'], '')
                result[host['id']] = host
            for id in iaas_9086_hosts:
                log.debug('handling IAAS-9086 for host %s' % id)
                _unauthorized_hosts.pop(id, None)
                _unauthorized_host_status_time.pop(id, None)
                _unauthorized_host_status_time_on_du.pop(id, None)

        if iaas_9086_hosts:
            iaas_9086_url = os.getenv('IAAS_9086_WEBHOOK_URL')
            if iaas_9086_url:
                payload = {
                    "text": "IAAS-9086 detected on hosts %s" % iaas_9086_hosts
                }
                try:
                    requests.post(iaas_9086_url, json=payload)
                except:
                    log.warn('warning: failed to post to %s', iaas_9086_url)

        return result

    def get_host_cert_info(self, host_id):
        """
        Get certificate information for the specified host
        :param str host_id: ID of the host
        :return: dictionary of the host attributes
        :rtype: dict
        :raises HostNotFound: if the host is not present
        """
        if host_id in _hosts_cert_data:
            host_cert_info = _hosts_cert_data.get(host_id, '')
            return host_cert_info
        else:
            log.error('Host %s is not a recognized host', host_id)
            raise HostNotFound(host_id)

    def get_host(self, host_id):
        """
        Get information for a host
        :param str host_id: ID of the host
        :return: dictionary of the host attributes
        :rtype: dict
        """
        # Check if the host is in the authorized host list first
        result = self.get_authorized_host(host_id)
        if not result:
            # If not found in the authorized host list, look up the unauthorized
            # host list.
            with _host_lock:
                if host_id in _unauthorized_hosts:
                    log.info('Found %s in unauthorized hosts', host_id)
                    result = _unauthorized_hosts[host_id]
                    result['hypervisor_info'] = _hosts_hypervisor_info.get(host_id, '')
                    result['extensions'] = _hosts_extension_data.get(host_id, '')
                    result['cert_info'] = _hosts_cert_data.get(host_id, '')

        return result

    def get_authorized_host(self, host_id):
        """
        Get information for an authorized host. Returns empty dict if the host
        is not present in the list of authorized hosts.
        :param str host_id: ID of the host
        :return: dictionary of the host attributes. Empty dict if host is not
        found in the list of authorized hosts.
        :rtype: dict
        """
        host = self.db_handler.query_host(host_id)
        if host:
            if _authorized_host_role_status.get(host_id):
                host['role_status'] = _authorized_host_role_status[host_id]
            host['hypervisor_info'] = _hosts_hypervisor_info.get(host['id'], '')
            host['extensions'] = _hosts_extension_data.get(host['id'], '')
            host['cert_info'] = _hosts_cert_data.get(host['id'], '')
            return host

        return {}

class BbonePoller(object):
    """
    Poller class that queries backbone for host state and updates the resource
    manager's state (both in DB and memory)
    """
    def __init__(self, config, db_handle, rolemgr, notifier):
        """
        Constructor
        :param ConfigParser config: Config Parser object from resource manager
        :param ResMgrDB db_handle: Handle to the resource manager database
        :param RolesMgr rolemgr: RolesMgr object
        :param notifier notifier: The notifier object
        """
        self.config = config
        self.db_handle = db_handle
        self.rolemgr = rolemgr
        # Backbone polling interval, in seconds
        self.poll_interval = config.getint('backbone', 'pollInterval')
        self.bbone_endpoint = config.get('backbone', 'endpointURI')
        self.notifier = notifier
        # The default threshold time after which not responding hosts should
        # be removed, in seconds
        default_non_responsive_host_threshold = config.getint(
                                            'resmgr', 'defaultNonResponsiveHostThreshold')
        # The threshold time after which not responding hosts that are
        # converging should be removed, in seconds
        converging_non_responsive_host_threshold = config.getint(
                                            'resmgr', 'convergingNonResponsiveHostThreshold')
        self.default_non_responsive_host_timeout = datetime.timedelta(
                                            seconds=default_non_responsive_host_threshold)
        self.converging_non_responsive_host_timeout = datetime.timedelta(
                                            seconds=converging_non_responsive_host_threshold)

        # allows us to wake up the bbone poller on demand
        self._command_queue = Queue()

    def _responding_within_threshold(self,
                                    status_time,
                                    threshold=None):
        """
        Checks if the provided status time is beyond the specified threshold
        time, wrt the current time
        :param datetime status_time: status time to be compared with
        :param int threshold: specifies the threshold time, in seconds
        :return: True if time is within the threshold, else False
        """
        if not threshold:
            threshold = self.default_non_responsive_host_timeout
        current_time = datetime.datetime.utcnow()
        time_delta = current_time - status_time
        return time_delta < threshold and -time_delta < threshold

    def _add_host_message(self, host_id, level, msg):
        if host_id not in _hosts_message_data:
            _hosts_message_data[host_id] = {}
        message = _hosts_message_data[host_id]

        if level not in message:
            message[level] = []
        message_list = message[level]

        if msg not in message_list:
            message_list.append(msg)

    def _remove_host_message(self, host_id, level, msg):
        if host_id not in _hosts_message_data:
            return
        message = _hosts_message_data[host_id]

        if level not in message:
            return
        if msg in message[level]:
            message[level].remove(msg)

    def _get_backbone_host(self, host):
        return call_remote_service('%s/v1/hosts/%s' %
                                   (self.bbone_endpoint, host))

    def _get_backbone_host_ids(self):
        return set(call_remote_service('%s/v1/hosts/ids' %
                                       self.bbone_endpoint))

    def _process_new_hosts(self, host_ids):
        """
        Process hosts that are reported by backbone but are not present in resource
        manager's state
        :param list host_ids: list of host IDs
        """
        # These hosts are new from the DB point of view. Such hosts have to
        # start in the unauthorized bucket
        for host in host_ids:
            try:
                host_info = self._get_backbone_host(host)
            except BBMasterNotFound:
                log.exception('Querying backbone for %s failed', host)
                continue

            if host_info['status'] == 'missing' or 'info' not in iterkeys(host_info):
                # If host status is missing, do nothing.
                continue

            unauth_host = {
                'id': host,
                'roles': [],
                'info': host_info['info']
            }

            status_time = datetime.datetime.strptime(host_info['timestamp'],
                                                     "%Y-%m-%d %H:%M:%S.%f")
            host_responding = self._responding_within_threshold(status_time)

            status_time_on_du = datetime.datetime.strptime(host_info['timestamp_on_du'],
                                                           "%Y-%m-%d %H:%M:%S.%f")
            host_on_du_responding = self._responding_within_threshold(status_time_on_du)

            if not host_responding and host_on_du_responding:
                self._add_host_message(host, TIMEDRIFT_MSG_LEVEL, TIMEDRIFT_MSG)
            elif not host_responding:
                continue

            # TODO: There is a potential case here where we want to clear out remnant
            # roles (pf9apps) from a newly/unauthorized hosts.

            # assignment to _unauthorized_* dicts is atomic. There is no need
            # for a lock here.
            # See http://effbot.org/pyfaq/what-kinds-of-global-value-mutation-are-thread-safe.htm
            log.info('adding new host %s to unauthorized hosts', unauth_host)
            _unauthorized_hosts[host] = unauth_host
            _unauthorized_host_status_time[host] = status_time
            _unauthorized_host_status_time_on_du[host] = status_time_on_du
            _hosts_hypervisor_info[host] = host_info.get('hypervisor_info', '')
            _hosts_extension_data[host] = host_info.get('extensions', '')
            _hosts_cert_data[host] = host_info.get('cert_info', '')


            # Trigger the notifier so that clients know about it.
            self.notifier.publish_notification('add', 'host', host)

    def _process_absent_hosts(self, host_ids, authorized_hosts):
        """
        Process hosts that are present in our state but are not being processed
        by backbone
        :param list host_ids: List of host ids
        :param dict authorized_hosts: details of the authorized hosts
        """
        for host in host_ids:
            with _host_lock:
                if host in _unauthorized_hosts:
                    log.warn("Unauthorized host being removed: %s", host)
                    _remove_all_host_metrics(id, _unauthorized_hosts[id]['info']['hostname'])
                    _unauthorized_hosts.pop(host, None)
                    _unauthorized_host_status_time.pop(host, None)
                    _unauthorized_host_status_time_on_du.pop(host, None)
                    _hosts_hypervisor_info.pop(host, None)
                    _hosts_extension_data.pop(host, None)
                    _hosts_cert_data.pop(host, None)
                    self.notifier.publish_notification('delete', 'host', host)
                    continue

            with _role_update_lock:
                # There may be hosts that need to be deauthorized but are offline (and
                # bbmaster may be unaware of them anymore). Such hosts appear in the
                # absent host list. We should try to transition them through the resmgr
                # state machine.
                self._advance_from_transient_state(host,
                                                   authorized_hosts.get(host))

            if host in authorized_hosts and authorized_hosts[host]['responding']:
                log.info('Host %s being marked as not responding', host)
                self.db_handle.mark_host_state(host, responding=False)
                _record_host_up_metric(0, host,
                                       authorized_hosts[host]['hostname'])
                self.notifier.publish_notification('change', 'host', host)

    def _update_role_status(self, host_id, host):
        """
        Calculate role status based on both the response from bbmaster and
        the host roles state machine states.
        """
        role_assocs = self.db_handle.get_all_role_associations(host_id)
        states = [assoc.current_state for assoc in role_assocs]
        if any([role_states.role_is_failed(str(s)) for s in states]):
            host_status = 'failed'
        elif any([role_states.role_is_converging(str(s)) for s in states]):
            host_status = 'converging'
        else:
            host_status = host['status']

        if _authorized_host_role_status.get(host_id) != host_status:
            _authorized_host_role_status[host_id] = host_status
            self.notifier.publish_notification('change', 'host', host_id)

    def _process_existing_hosts(self, host_ids, authorized_hosts):
        """
        Process hosts that are reported by backbone and is also tracked in our state
        :param list host_ids: list of host ids
        :param dict authorized_hosts: details of the authorized hosts
        """
        for host in host_ids:
            with _role_update_lock:
                self._advance_from_transient_state(host,
                                                   authorized_hosts.get(host))
            try:
                host_info = self._get_backbone_host(host)
            except BBMasterNotFound:
                log.exception('Querying backbone for %s failed', host)
                # TODO: Should we return instead of continuing here?
                continue

            status_time = datetime.datetime.strptime(host_info['timestamp'],
                                                     "%Y-%m-%d %H:%M:%S.%f")
            status_time_on_du = datetime.datetime.strptime(host_info['timestamp_on_du'],
                                                           "%Y-%m-%d %H:%M:%S.%f")

            try:
                hostname = host_info['info']['hostname']
            except KeyError:
                hostname = None
            _hosts_hypervisor_info[host] = host_info.get('hypervisor_info', '')
            _hosts_extension_data[host] = host_info.get('extensions', '')
            _hosts_cert_data[host] = host_info.get('cert_info')

            host_status = host_info['status']
            if host_status in ('converging', 'retrying'):
                responding_threshold = self.converging_non_responsive_host_timeout
            else:
                responding_threshold = self.default_non_responsive_host_timeout
            responding = self._responding_within_threshold(status_time,
                                                           responding_threshold)
            if responding:
                self._remove_host_message(host, TIMEDRIFT_MSG_LEVEL, TIMEDRIFT_MSG)
                responding_on_du = True
            else:
                responding_on_du = self._responding_within_threshold(status_time_on_du,
                                                                     responding_threshold)
                if responding_on_du:
                    self._add_host_message(host, TIMEDRIFT_MSG_LEVEL, TIMEDRIFT_MSG)
            if host in authorized_hosts:
                if authorized_hosts[host]['responding'] != (responding or responding_on_du):
                    # If host status is responding and is marked as not
                    # responding, tag it as responding. And vice versa
                    self.db_handle.mark_host_state(host, responding=(responding or responding_on_du))
                    _record_host_up_metric(int(responding or responding_on_du), host,
                                           authorized_hosts[host]['hostname'])
                    self.notifier.publish_notification('change', 'host', host)
                    log.info('Marking %s as %s responding, status time: %s',
                             host, '' if (responding or responding_on_du) else 'not', host_info['timestamp'])

                # Active hosts but we need to change the configuration
                try:
                    if self.rolemgr.received_since_last_push(host, host_info) and \
                       host_status not in ('ok', 'retrying', 'converging', 'missing'):
                        # put the roles that were converging into the failed state and
                        # continue to other hosts
                        self._fail_role_converge(host)
                    elif not (responding or responding_on_du):
                        # if we're waiting for convergence, assume we'll never see it,
                        # finish setup/cleanup with on post converge event handlers.
                        self._finish_role_converge(host, authorized_hosts[host])
                    else:
                        cfg_key = 'apps' if host_status == 'ok' else 'desired_apps'
                        host_config = host_info.get(cfg_key, {})
                        # if host_status is 'ok'
                        # Check if app status in the DB is same as the app config
                        # in the result
                        # if host_status is 'retrying' or 'converging'
                        # Check if desired app status in result is same as app status
                        # in DB
                        # TODO: Cross check if this is intended design
                        expected_cfg = authorized_hosts[host]['apps_config']
                        role_settings = authorized_hosts[host]['role_settings']
                        roles = self.rolemgr.db_handler.query_roles_for_host(host)
                        if roles:
                            _update_custom_role_settings(expected_cfg, role_settings, roles)
                        if self.rolemgr.received_since_last_push(host, host_info) and \
                           host_status == 'ok' and \
                           is_satisfied_by(expected_cfg, host_info['apps']):
                            self._finish_role_converge(host,
                                                       authorized_hosts[host])
                        elif not is_satisfied_by(expected_cfg, host_config):
                            log.debug('Pushing new configuration for %s, config: %s. '
                                      'Expected config %s', host, host_config,
                                      expected_cfg)
                            self.rolemgr.push_configuration(host, expected_cfg)
                    self._update_role_status(host, host_info)

                    if 'info' not in host_info:
                        return

                    # Host OS info as reported from bbmaster
                    current_host_info = {
                        'hostarch': host_info['info'].get('arch'),
                        'hostname': host_info['info'].get('hostname'),
                        'hostosfamily': host_info['info'].get('os_family'),
                        'hostosinfo': host_info['info'].get('os_info'),
                    }

                    # Compare host info from bbmaster to values stored in resmgr
                    updated_host_info = { k: v for k, v in iteritems(current_host_info)
                        if authorized_hosts[host][k] != v }

                    # Update resmgr DB if host info has changed
                    if updated_host_info:
                        self.db_handle.update_host_info(host, updated_host_info)
                        self.notifier.publish_notification('change', 'host', host)

                except (BBMasterNotFound, HostConfigFailed):
                    log.exception('Backbone request for %s failed', host)
                    continue
            else:
                # assignment to _unauthorized_* dicts is atomic. There is no need
                # for a lock here.
                # See http://effbot.org/pyfaq/what-kinds-of-global-value-mutation-are-thread-safe.htm
                _unauthorized_host_status_time[host] = status_time
                _unauthorized_host_status_time_on_du[host] = status_time_on_du
                # TODO: Is there a need to update the unauthorized hosts with more data
                # returned from bbone?
                if hostname and _unauthorized_hosts[host]['info']['hostname'] != hostname:
                    _unauthorized_hosts[host]['info']['hostname'] = hostname
                    self.notifier.publish_notification('change', 'host', host)

    def _finish_role_converge(self, host_id, host_details):
        db = self.db_handle
        roles = db.query_roles_for_host(host_id)
        if not roles:
            return
        for role in roles:
            try:
                if db.advance_role_state(host_id, role.rolename,
                                         role_states.AUTH_CONVERGING,
                                         role_states.AUTH_CONVERGED):
                    self.rolemgr.move_to_applied_state(host_id, host_details,
                                                       role.rolename)
                elif db.advance_role_state(host_id, role.rolename,
                                           role_states.DEAUTH_CONVERGING,
                                           role_states.DEAUTH_CONVERGED):
                    self.rolemgr.move_to_not_applied_state(host_id, host_details,
                                                           role.rolename)
            except DuConfigError as e:
                log.error('Failed to run post converge event for role %s on '
                          'host %s: %s', role.rolename, host_id, e)

    def _fail_role_converge(self, host_id):
        """
        After a host convergence failure (host itself gave up on convergence),
        move to the AUTH_CONVERGE_FAILED or DEAUTH_CONVERGE_FAILED state. This
        will allow the user to do a new PUT or DELETE on the role.
        """
        db = self.db_handle
        for role in db.query_roles_for_host(host_id):
            if db.advance_role_state(host_id, role.rolename,
                                     role_states.AUTH_CONVERGING,
                                     role_states.AUTH_ERROR):
                log.info('Moved role %s on host %s to the %s state',
                         role.rolename, host_id, role_states.AUTH_ERROR)
            elif db.advance_role_state(host_id, role.rolename,
                                       role_states.DEAUTH_CONVERGING,
                                       role_states.DEAUTH_ERROR):
                log.info('Moved role %s on host %s to the %s state',
                         role.rolename, host_id, role_states.DEAUTH_ERROR)

    def _advance_from_transient_state(self, host_id, host_details):
        """
        Move the state machine forward to a point where it's either waiting
        for status from a host, or at a terminal state. This comes into effect
        either after a new API request to add/delete a role, or when the resmgr
        is restarted after a crash that leaves a role in a transient state.
        From here, the state machine can be moved forward by add/delete if it's
        in a terminal state, or by _process_existing_hosts when new info is
        pulled from a host.
        FIXME: With a bit more refactoring, this could handle the whole state
               machine.
        """
        if not host_details:
            return
        db = self.db_handle
        roles = host_details['role_details']
        rolenames = [r.rolename for r in roles] if roles else []
        for rolename in rolenames:
            more_transitions = True
            while more_transitions:
                assoc = db.get_current_role_association(host_id, rolename)
                if not assoc:
                    break
                current_state = assoc.current_state
                if current_state in [role_states.START_APPLY,
                                     role_states.START_EDIT]:
                    self.rolemgr.move_to_preauth_state(host_id, host_details,
                                                       rolename, current_state)
                elif current_state == role_states.PRE_AUTH:
                    self.rolemgr.move_to_auth_converging_state(host_id,
                                                               host_details,
                                                               rolename)
                elif current_state == role_states.AUTH_CONVERGED:
                    self.rolemgr.move_to_applied_state(host_id, host_details,
                                                       rolename)
                    more_transitions = False
                elif current_state == role_states.START_DEAUTH:
                    self.rolemgr.move_to_pre_deauth_state(host_id,
                                                          host_details,
                                                          rolename,
                                                          current_state)
                elif current_state == role_states.PRE_DEAUTH:
                    self.rolemgr.move_to_deauth_converging_state(host_id,
                                                                 host_details,
                                                                 rolename)
                elif current_state == role_states.DEAUTH_CONVERGED:
                    self.rolemgr.move_to_not_applied_state(host_id,
                                                           host_details,
                                                           rolename)
                    more_transitions = False
                else:
                    more_transitions = False

    def _cleanup_unauthorized_hosts(self):
        """
        Cleanup unauthorized hosts that have not reported a status message
        within the status time.
        """
        cleanup_hosts = []
        with _host_lock:
            for id in iterkeys(_unauthorized_hosts):
                if not (self._responding_within_threshold(_unauthorized_host_status_time[id])
                        or self._responding_within_threshold(_unauthorized_host_status_time_on_du[id])):
                    # Maintain a list of hosts that are past the threshold
                    cleanup_hosts.append(id)

            if cleanup_hosts:
                log.warn("Unauthorized hosts that are being removed: %s", cleanup_hosts)

            for id in cleanup_hosts:
                _remove_all_host_metrics(id, _unauthorized_hosts[id]['info']['hostname'])
                _unauthorized_hosts.pop(id, None)
                _unauthorized_host_status_time.pop(id, None)
                _unauthorized_host_status_time_on_du.pop(id, None)
                _hosts_message_data.pop(id, None)
                self.notifier.publish_notification('delete', 'host', id)

    def process_metrics(self):
        authorized_hosts = self.db_handle.query_host_and_app_details()

        for ak, av in authorized_hosts.items():
            _record_host_up_metric(av['responding'], ak, av['hostname'])
            _record_host_converged_metric(_authorized_host_role_status.get(ak, 'unknown') == 'ok',
                                          ak, av['hostname'])

            ispmkhost = False
            for r in av['role_details']:
                if r.rolename == 'pf9-kube':
                    ispmkhost = True
                    break
            _record_host_has_pmk_role_metric(ispmkhost, ak ,av['hostname'])
            # Process the host cert related metrics
            if ak in _hosts_cert_data:
                cert_info = _hosts_cert_data.get(ak, '')
                if cert_info:
                    _record_host_cert_metrics(cert_info, ak, av['hostname'])

        for uk, uv in _unauthorized_hosts.items():
            _record_host_up_metric(1, uk, uv['info']['hostname'])
            if uk in _hosts_cert_data:
                cert_info = _hosts_cert_data.get(uk, '')
                if cert_info:
                    _record_host_cert_metrics(cert_info, uk,
                                        uv['info']['hostname'])

    def process_hosts(self, post_db_read_hook_func=None):
        """
        Routine to query bbone for host info and process it
        """
        try:
            bbone_ids = self._get_backbone_host_ids()
        except BBMasterNotFound:
            log.exception('Querying backbone for hosts failed')
        else:
            # Get authorized host ids and unauthorized host ids and store it
            # in all_ids
            authorized_hosts = self.db_handle.query_host_and_app_details()
            all_ids = set(list(iterkeys(authorized_hosts)) + list(iterkeys(_unauthorized_hosts)))
            new_ids = bbone_ids - all_ids
            del_ids = all_ids - bbone_ids
            exist_ids = all_ids & bbone_ids

            # This hook is for simulating a race condition that modifies the
            # app config database after it's read at the top of this method.
            # Currently used by the unit-test for CORE-646
            if post_db_read_hook_func:
                post_db_read_hook_func()

            # Process hosts that are newly reported from backbone
            self._process_new_hosts(new_ids)
            # Process hosts that backbone claims are not present anymore(?)
            self._process_absent_hosts(del_ids, authorized_hosts)
            # Deal with changes to existing hosts
            self._process_existing_hosts(exist_ids, authorized_hosts)
            # Cleanup older unauthorized hosts
            self._cleanup_unauthorized_hosts()

            # Process metrics at the end of the loop
            self.process_metrics()

    def run(self):
        """
        Main poller routine
        """
        log.debug('start backbone poll routine')
        while (True):
            # Get the host ids that backbone is aware of
            try:
                self.process_hosts()
                command = self._command_queue.get(block=True,
                                                  timeout=self.poll_interval)
                if command == 'stop':
                    log.debug('Stopping bbone poller')
                    break
                elif command == 'wake':
                    log.debug('Running bbone poll after a request')
            except Empty:
                log.debug('Running bbone poller again after %d seconds',
                          self.poll_interval)
            except:
                # Ensure that this poller will never go down.
                # Log and continue
                log.exception('Poller encountered an error')

    def wake_up(self):
        self._command_queue.put('wake')

    def stop(self):
        self._command_queue.put('stop')

class ResMgrPf9Provider(ResMgrProvider):
    """
    Implementation of the ResMgrProvider interface
    """
    def __init__(self, config_file):
        """
        Constructor
        :param str config_file: Path to configuration file for resource manager
        """
        config = self._load_config(config_file)

        self.res_mgr_db = ResMgrDB(config)
        self.host_inventory_mgr = HostInventoryMgr(config, self.res_mgr_db)
        self.roles_mgr = RolesMgr(config, self.res_mgr_db)
        notifier.init(log, config)

        self._rabbit_mgmt_cl = self.roles_mgr.rabbit_mgmt_cl
        self.setup_rabbit_credentials()
        self.bb_url = config.get('backbone', 'endpointURI')

        self.run_service_config()

        # Setup a thread to poll backbone state regularly to detect changes to
        # hosts.
        # FIXME: The provider loop is now controlled with a command Queue. Add
        # a sighandler to send a 'stop' to the poller and join the thread
        # rather than making it a daemon.
        self.bbone_poller = BbonePoller(config, self.res_mgr_db,
                                        self.roles_mgr, notifier)
        t = threading.Thread(target=self.bbone_poller.run)
        t.daemon = True
        t.start()

        try:
            self._consul_roles = ConsulRoles(config, self.res_mgr_db)
            self._consul_roles.startwatch()
        except ConsulUnavailable as e:
            log.info('Consul isn\'t available. Roles are loaded from the '
                     'filesystem only: %s', e)

    @staticmethod
    def _load_config(config_file):
        """
        Load the config file as well as the global config file.
        """
        config = ConfigParser()
        config.read(config_file)
        global_cfg_file = config.get('resmgr', 'global_config_file')
        config.read(global_cfg_file)
        role_metadata_dir = config.get('resmgr', 'role_metadata_location')
        _load_role_confd_files(role_metadata_dir, config)
        return config

    def run_service_config(self):
        svcs = self.res_mgr_db.get_service_configs()

        for s in svcs:
            log.info('Running service config for %s at startup', s['service_name'])
            try:
                _run_script([s['config_script_path'], json.dumps(s['settings'])])
            except:
                log.exception('Running script %s failed', s['config_script_path'])

    def setup_rabbit_credentials(self):
        """
        Sync the rabbit_credentials table with the actual RabbitMQ list
        of users.
        """
        log.info('Adding RabbitMQ users from the rabbit_credentials table')

        # Maps roles to rabbit permissions
        rabbit_permissions_map = {}
        for role in self.res_mgr_db.query_roles():
            rabbit_permissions_map[role.rolename] = role.rabbit_permissions

        for credential in self.res_mgr_db.query_rabbit_credentials():
            rabbit_permissions = rabbit_permissions_map[credential.rolename]
            self._rabbit_mgmt_cl.create_user(credential.userid,
                                             credential.password)
            self._rabbit_mgmt_cl.set_permissions(credential.userid,
                                                 rabbit_permissions['config'],
                                                 rabbit_permissions['write'],
                                                 rabbit_permissions['read'])

    def request_support_bundle(self, host_id, body):
        url = "%s/v1/hosts/%s/support/bundle" % (self.bb_url, host_id)
        try:
            r = requests.post(url, data=json.dumps(body))
            if r.status_code != requests.codes.ok:
                raise SupportRequestFailed('Error in POST request response: %d, host %s' %
                                           (r.status_code, host_id))

        except requests.exceptions.RequestException as exc:
            log.error('Getting support for host %s failed: %s', host_id, exc)
            raise BBMasterNotFound(exc)

    def run_support_command(self, host_id, body):
        url = "%s/v1/hosts/%s/support/command" % (self.bb_url, host_id)
        try:
            r = requests.post(url, data=json.dumps(body))
            if r.status_code != requests.codes.ok:
                raise SupportCommandRequestFailed('Error in POST request response: %d, host %s' %
                                           (r.status_code, host_id))

        except requests.exceptions.RequestException as exc:
            raise BBMasterNotFound(exc)

    def get_cert_info(self, host_id):
        """
        Returns certificate information about a host
        :param str host_id: ID of the host
        :return: dictionary containing certificate info of the host
        :rtype: dict
        """
        return self.host_inventory_mgr.get_host_cert_info(host_id)

    def request_cert_refresh(self, host_id):
        """
        Sends a request for certificate update on the host
        :param str host_id: ID of the host
        :return: None
        :raises: CertRefreshRequestFailed If unable to send cert refresf request
        :raises: BBMasterNotFound If communication to the backbone fails
        """
        url = "%s/v1/hosts/%s/certs" % (self.bb_url, host_id)
        try:
            r = requests.put(url)
            if r.status_code != requests.codes.ok:
                raise CertRefreshRequestFailed('Error in PUT request response: %d, host %s' %
                                            (r.status_code, host_id))
        except requests.exceptions.RequestException as exc:
            raise BBMasterNotFound(exc)

    def get_all_roles(self):
        """
        Returns information about all known roles
        :return: dictionary of roles and their information
        :rtype: dict
        """
        return self.roles_mgr.get_all_roles()

    def get_role(self, role_name):
        """
        Returns all information about an active role
        :param str role_name: Name of the role
        :return: dictionary of the role information
        :rtype: dict
        """
        return self.roles_mgr.get_role(role_name)

    def get_role_with_version(self, role_name, version):
        """
        Returns all information about a role with given version
        :param str role_name: Name of the role
        :param str version: Version of the role
        :return: dictionary of the role information
        :rtype: dict
        """
        return self.roles_mgr.get_role_with_version(role_name, version)

    def mark_role_version_active(self, role_name, version, active):
        """
        Marks a role with given version as active
        :param role_name: Name of the role
        :param version: version of the role
        :param active: Flag indicating if the role is to marked as active.
        """
        return self.roles_mgr.mark_role_version_active(role_name, version,
                                                       active)

    def create_role(self, role_info):
        """
        Creates a role with incoming role information and stores
        this role in the database.
        :param role_info : JSON with role information.
        """
        return self.roles_mgr.create_role(role_info)

    def get_app_versions(self, role_name):
        return self.roles_mgr.get_app_versions(role_name)

    def get_all_hosts(self, role_settings=False):
        """
        Returns information about all known hosts
        :return: dictionary of hosts and their information
        :rtype: dict
        """
        return self.host_inventory_mgr.get_all_hosts(
            role_settings=role_settings)

    def get_host(self, host_id):
        """
        Returns all information about a host
        :param str host_id: ID of the host
        :return: dictionary of the host information
        :rtype: dict
        """
        return self.host_inventory_mgr.get_host(host_id)

    def delete_host(self, host_id):
        """
        Delete a host state
        :param str host_id: ID of the host
        :raises HostNotFound: if the host is not present
        :raises HostConfigFailed: if setting the configuration fails or times out
        :raises BBMasterNotFound: if communication to the backbone fails
        """
        if host_id in _unauthorized_hosts:
            log.warn('Host %s is classified as unauthorized host. Nothing '
                     'to delete', host_id)
            return

        # Delete all the roles for the host
        host_inst = self.host_inventory_mgr.get_authorized_host(host_id)
        if not host_inst:
            log.error('Host %s not found in the authorized host list', host_id)
            raise HostNotFound(host_id)

        # Clear out all the roles
        for role in self.res_mgr_db.query_roles_for_host(host_id):
            self.delete_role(host_id, role.rolename, wake_poller=False)

        self.bbone_poller.wake_up()

    def _random_rabbit_creds(self, len=16):
        return tuple(
            "".join([random.choice(string.ascii_letters + string.digits)
                     for i in range(len)])
            for j in range(2)
        )

    def create_rabbit_credentials(self, host_id, role_name, version):
        """
        Get the credentials for the specified host and role from the database.
        If no credentials are found, then they are created.
        """
        credentials = self.res_mgr_db.query_rabbit_credentials(host_id=host_id,
                                                               rolename=role_name)
        if credentials:
            if len(credentials) != 1:
                msg = ('Invalid number of rabbit credentials for host %s and role %s'
                       % (host_id, role_name))
                log.error(msg)
                raise RabbitCredentialsConfigureError(msg)
            credential = credentials[0]
            rabbit_user = credential.userid
            rabbit_password = credential.password
        else:
            rabbit_user, rabbit_password = self._random_rabbit_creds()
        self._rabbit_mgmt_cl.create_user(rabbit_user, rabbit_password)
        if not version:
            associated_role = self.res_mgr_db.query_role(role_name)
        else:
            associated_role = self.res_mgr_db.query_role_with_version(role_name, version)

        permissions = associated_role.rabbit_permissions
        try:
            self._rabbit_mgmt_cl.set_permissions(rabbit_user,
                                                 permissions['config'],
                                                 permissions['write'],
                                                 permissions['read'])
        except:
            self._rabbit_mgmt_cl.delete_user(rabbit_user)
            msg = ('Failed to set RabbitMQ user permissions for host %s and role %s'
                   % (host_id, role_name))
            log.exception(msg)
            raise RabbitCredentialsConfigureError(msg)
        return rabbit_user, rabbit_password

    def _move_to_apply_edit_state(self, host_id, role_name):
        curr_state = None
        if self.res_mgr_db.advance_role_state(host_id, role_name,
                role_states.NOT_APPLIED, role_states.START_APPLY):
            log.debug('role %s on host %s moved from %s to %s', role_name,
                      host_id, role_states.NOT_APPLIED, role_states.START_APPLY)
            log.info('Applying role %s to %s', role_name, host_id)
            curr_state = role_states.START_APPLY
        elif self.res_mgr_db.advance_role_state(host_id, role_name,
                role_states.APPLIED, role_states.START_EDIT):
            log.debug('role %s on host %s moved from %s to %s', role_name,
                      host_id, role_states.APPLIED, role_states.START_EDIT)
            log.info('Editing role %s on %s', role_name, host_id)
            curr_state = role_states.START_EDIT
        elif self.res_mgr_db.advance_role_state(host_id, role_name,
                role_states.AUTH_ERROR, role_states.START_APPLY):
            log.debug('role %s on host %s moved from %s to %s', role_name,
                      host_id, role_states.AUTH_ERROR, role_states.START_APPLY)
            log.info('Editing role %s on %s', role_name, host_id)
            curr_state = role_states.START_APPLY
        else:
            raise RoleUpdateConflict('Cannot add role %s to host %s in the '
                                     'current state.' % (role_name, host_id))
        return curr_state

    def _move_to_deauth_state(self, host_id, role_name):
        curr_state = None
        if self.res_mgr_db.advance_role_state(host_id, role_name,
                role_states.APPLIED, role_states.START_DEAUTH):
            log.info('role %s on host %s moved from %s to %s', role_name,
                     host_id, role_states.APPLIED, role_states.START_DEAUTH)
            log.info('Removing role %s from %s', role_name, host_id)
            curr_state = role_states.START_DEAUTH
        elif self.res_mgr_db.advance_role_state(host_id, role_name,
                role_states.DEAUTH_ERROR, role_states.START_DEAUTH):
            log.info('role %s on host %s moved from %s to %s', role_name,
                     host_id, role_states.DEAUTH_ERROR, role_states.START_DEAUTH)
            curr_state = role_states.START_DEAUTH
        elif self.res_mgr_db.advance_role_state(host_id, role_name,
                role_states.AUTH_ERROR, role_states.START_DEAUTH):
            log.info('role %s on host %s moved from %s to %s', role_name,
                     host_id, role_states.AUTH_ERROR, role_states.START_DEAUTH)
            curr_state = role_states.START_DEAUTH
        else:
            raise RoleUpdateConflict('Cannot remove role %s from host %s in the '
                                     'current state.' % (role_name, host_id))
        return curr_state

    def add_role(self, host_id, role_name, version, host_settings):
        """
        Add a role to a particular host
        :param str host_id: ID of the host
        :param str role_name: Name of the role
        :param dict host_settings: The custom host settings for the specified role.
        :raises RoleNotFound: if the role is not present
        :raises HostNotFound: if the host is not present
        :raises HostConfigFailed: if setting the configuration fails or times out
        :raises DuConfigError: If the on_auth event for the role fails.
        :raises BBMasterNotFound: if communication to the backbone fails
        """
        log.info('Assigning role %s to %s with host settings %s',
                 role_name, host_id, host_settings)

        if not version:
            active_role_in_db = self.res_mgr_db.query_role(role_name)
            if not active_role_in_db:
                log.error('Role %s is not found in list of active roles', role_name)
                raise RoleNotFound(role_name)
        else:
            role_in_db = self.res_mgr_db.query_role_with_version(role_name, version)
            if not role_in_db:
                log.error('Role %s, version %s is not found in the list of roles',
                          role_name, version)
                raise RoleVersionNotFound(role_name, version)

        host_inst = self.host_inventory_mgr.get_host(host_id)
        if not host_inst:
            log.error('Host %s is not a recognized host', host_id)
            raise HostNotFound(host_id)
        elif not host_inst.get('info', {}).get('responding', True):
            log.warn('Can\'t apply role %s to host %s: host is not responding',
                     role_name, host_id)
            raise HostDown('Applying %s to host %s' % (role_name, host_id))

        initially_inactive = not host_inst['roles']
        host_inst['roles'].append(role_name)
        _authorized_host_role_status[host_id] = None

        if initially_inactive:
            notifier.publish_notification('change', 'host', host_id)

        # 1. Record the role addition state in the DB
        # 2. Publish change notification
        # 3. Run on_auth event from configuration
        # 4. Push the new configuration to the host
        # Push configuration to bbone is idempotent, so we will end up with
        # a converged state eventually.

        log.debug('Updating host %s state after %s role association',
                  host_id, role_name)
        with _role_update_lock:
            try:
                role_is_new = False
                self.res_mgr_db.insert_update_host(host_id, host_inst['info'],
                                                   role_name, version, host_settings)
                role_is_new = self.res_mgr_db.associate_role_to_host(host_id,
                                                                     role_name,
                                                                     version)
                curr_role_state = self._move_to_apply_edit_state(host_id,
                                                                 role_name)
                with _host_lock:
                    # Once added to the DB, remove it from the unauthorized
                    # host dict. Note that we don't need to undo this in the
                    # exception handler; it's re-added by process_hosts
                    _unauthorized_hosts.pop(host_id, None)
                    _unauthorized_host_status_time.pop(host_id, None)
                    _unauthorized_host_status_time_on_du.pop(host_id, None)
                # IAAS-6519: rabbit changes after state machine starts
                rabbit_user, rabbit_password = \
                        self.create_rabbit_credentials(host_id, role_name, version)
                self.res_mgr_db.associate_rabbit_credentials_to_host(host_id,
                        role_name, rabbit_user, rabbit_password)
            except Exception as e:
                log.error('Host %s role \'%s\' add failed: %s', host_id,
                          role_name, e)
                if role_is_new:
                    self._rabbit_mgmt_cl.delete_user(rabbit_user)
                    self.res_mgr_db.remove_role_from_host(host_id, role_name)
                    if not self.res_mgr_db.query_roles_for_host(host_id):
                        # There is a chance that we are trying to delete a host when
                        # the host is offline. Remove the metrics entries too since
                        # the host will not become an unauthorized host prior to being
                        # removed.
                        _remove_all_host_metrics(host_id, host_inst['info']['hostname'])
                        self.res_mgr_db.delete_host(host_id)
                raise

            # run the on_auth event
            host_details = self.res_mgr_db.query_host_and_app_details(host_id)
            host_details = host_details[host_id]
            self.roles_mgr.move_to_preauth_state(host_id, host_details,
                                                 role_name, curr_role_state)
            # wake up the poller to start moving through the state machine.
            self.bbone_poller.wake_up()

            notifier.publish_notification('change', 'host', host_id)

    def delete_role(self, host_id, role_name, wake_poller=True):
        """
        Disassociates a role from a host.
        :param str host_id: ID of the host
        :param str role_name: Name of the role
        :param bool wake_poller: Wake up the bbone poller. When deleting a
            host with multiple roles, set this to False, then call
            poller.wake_up() explicitly after all the role deletes have been
            registered in the DB.
        :raises RoleNotFound: if the role is not present
        :raises HostNotFound: if the host is not present
        :raises HostConfigFailed: if setting the configuration fails or times out
        :raises BBMasterNotFound: if communication to the backbone fails
        :raises DuConfigError: If the on_deauth event for the role fails.
        """
        log.info('Removing role %s from %s', role_name, host_id)

        # FIXME - I think this can be removed. Not sure why we're not just
        # using the db state.
        if host_id in _unauthorized_hosts:
            log.warn('Host %s is classified as unauthorized host. Nothing '
                     'to delete', host_id)
            return
        active_role_in_db = self.res_mgr_db.query_role(role_name)
        if not active_role_in_db:
            log.error('Role %s is not found in list of active roles', role_name)
            raise RoleNotFound(role_name)

        with _role_update_lock:
            host_inst = self.host_inventory_mgr.get_host(host_id)
            if not host_inst:
                log.error('Host %s is not a recognized host', host_id)
                raise HostNotFound(host_id)

            if role_name not in host_inst['roles']:
                log.warn('Role %s is not assigned to %s', role_name, host_id)
                return

            curr_role_state = self._move_to_deauth_state(host_id, role_name)

            log.debug('Clearing role %s for host %s in DB', role_name, host_id)

            # run the on_deauth event
            host_details = self.res_mgr_db.query_host_and_app_details(host_id)
            host_details = host_details[host_id]
            self.roles_mgr.move_to_pre_deauth_state(host_id, host_details,
                                                    role_name, curr_role_state)
            # wake up the poller to start moving through the state machine.
            if wake_poller:
                self.bbone_poller.wake_up()

        notifier.publish_notification('change', 'host', host_id)

    def _invoke_service_cfg_script(self, service_name):
        svc_info = self.get_service_settings(service_name)
        if not svc_info:
            raise ServiceNotFound(service_name)

        try:
            _run_script([svc_info['config_script_path'],
                json.dumps(svc_info['settings'])])
        except Exception as e:
            raise ServiceConfigFailed(e)

    def set_service_settings(self, service_name, settings):
        """
        Update the DB with the settings for the service. Invoke the service
        configuration script following that.
        """
        self.res_mgr_db.update_service_settings(service_name, settings)
        self._invoke_service_cfg_script(service_name)

    def get_service_settings(self, service_name):
        """
        Get the service settings in the DB
        """
        return self.res_mgr_db.query_service_config(service_name)

    def get_custom_settings(self, host_id, role_name):
        return self.res_mgr_db.get_custom_settings(host_id, role_name)

def get_provider(config_file):
    return ResMgrPf9Provider(config_file)
