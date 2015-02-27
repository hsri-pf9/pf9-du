# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved

__author__ = 'Platform9'

"""
This module provides real implementation of Resource Manager provider interface
"""

import ConfigParser
import datetime
import logging
import json
import threading
import time
import rabbit
import random
import requests
import string
import dict_subst
import dict_tokens

from bbcommon.utils import is_satisfied_by
from dbutils import ResMgrDB
from exceptions import (BBMasterNotFound, HostNotFound, RoleNotFound,
                        HostConfigFailed, SupportRequestFailed,
                        SupportCommandRequestFailed, RabbitCredentialsConfigureError)
import notifier
from resmgr_provider import ResMgrProvider, RState

log = logging.getLogger('resmgr')

# Maintain some state for resource manager
_unauthorized_hosts = {}
_unauthorized_host_status_time = {}
_authorized_host_role_status = {}
_host_lock = threading.Lock()

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


def substitute_host_id(dictionary, host_id):
    """
    Replaces host ID tokens in a dictionary with actual host ID
    """
    token_map = {dict_tokens.HOST_ID_TOKEN: host_id}
    return dict_subst.substitute(dictionary, token_map)


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
    new_roles = dict((role.rolename, json.loads(role.customizable_settings)) for role in roles)

    # Iterate over all apps in app_info
    for given_app_name in app_info.keys():
        for role_name, settings in new_roles.iteritems():
            for setting_name, setting in settings.iteritems():
                # Role is considered only if it is part of the provided role_settings
                # AND part of the app name
                if role_name not in role_settings:
                    continue
                # TODO: We should really have a better way of making this association between app and role
                if given_app_name not in role_name:
                    continue
                path = setting['path'].split('/')
                # Traverse the config according to the path of the default setting.
                # Then, insert the custom role setting into the app info
                app_info_temp = app_info[given_app_name]
                for key in path:
                    app_info_temp = app_info_temp[key]
                app_info_temp[setting_name] = role_settings[role_name][setting_name]


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
        Returns information of all active roles
        :rtype: dict
        """
        query_op = self.db_handler.query_roles()
        result = {}
        for role in query_op:
            default_settings = dict((setting_name, setting['default'])
                                    for (setting_name, setting)
                                    in json.loads(role.customizable_settings).iteritems())
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
                                    in json.loads(role.customizable_settings).iteritems())
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
                'config': json.loads(role.desiredconfig)
            }

        return result

    def push_configuration(self, host_id, app_info,
                           needs_hostid_subst=True,
                           needs_rabbit_subst=True):
        """
        Push app configuration to backbone service
        :param str host_id: host identifier
        :param dict app_info: app information that needs to be set in the configuration
        :param bool needs_hostid_subst: replace host ID tokens with actual host ID
        :raises HostConfigFailed: if setting the configuration fails or times out
        :raises BBMasterNotFound: if communication to the backbone fails
        """
        if needs_hostid_subst:
            app_info = substitute_host_id(app_info, host_id)
        if needs_rabbit_subst:
            self.db_handler.substitute_rabbit_credentials(app_info, host_id)
        log.info('Applying configuration %s to %s', app_info, host_id)
        url = "%s/v1/hosts/%s/apps" % (self.bb_url, host_id)
        try:
            r = requests.put(url, json.dumps(app_info))

            if r.status_code != requests.codes.ok:
                log.error('PUT request failed, response status code %d', r.status_code)
                raise HostConfigFailed('Error in PUT request response: %d' % r.status_code)

        except requests.exceptions.RequestException as exc:
            log.error('Configuring host %s failed: %s', host_id, exc)
            raise BBMasterNotFound(exc)


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

    def get_all_hosts(self):
        """
        Returns information about all known hosts.
        :rtype: dict:
        """
        result = {}
        query_op = self.db_handler.query_hosts()
        for host in query_op:
            host['state'] = RState.active if host['roles'] else RState.inactive
            if _authorized_host_role_status.get(host['id']):
                host['role_status'] = _authorized_host_role_status[host['id']]
            result[host['id']] = host

        # Add unauthorized hosts into the result
        log.debug('Looking up unauthorized hosts')
        # Access to unauthorized hosts here is atomic. Don't need a lock
        # for that purpose.
        result.update(_unauthorized_hosts)

        return result

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
            host['state'] = RState.active if host['roles'] else RState.inactive
            if _authorized_host_role_status.get(host_id):
                host['role_status'] = _authorized_host_role_status[host_id]
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
        # Threshold time after which not responding hosts should be removed, in seconds
        non_responsive_host_threshold = config.getint('resmgr', 'nonResponsiveHostThreshold')
        self.non_responsive_host_timeout = datetime.timedelta(
                                            seconds=non_responsive_host_threshold)

    def _responding_within_threshold(self, status_time):
        """
        Checks if the provided status time is beyond the non responsive threshold
        time, wrt the current time
        :param datetime status_time: status time to be compared with
        :return: True if time is within the threshold, else False
        """
        current_time = datetime.datetime.utcnow()
        time_delta = current_time - status_time
        return time_delta < self.non_responsive_host_timeout

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
                host_info = call_remote_service('%s/v1/hosts/%s' %
                                                (self.bbone_endpoint, host))
            except BBMasterNotFound:
                log.exception('Querying backbone for %s failed', host)
                continue

            if host_info['status'] == 'missing' or 'info' not in host_info.keys():
                # If host status is missing, do nothing.
                continue

            unauth_host = {
                'id': host,
                'roles': [],
                'state': RState.inactive,
                'info': host_info['info']
            }

            status_time = datetime.datetime.strptime(host_info['timestamp'],
                                                     "%Y-%m-%d %H:%M:%S.%f")


            if not self._responding_within_threshold(status_time):
                # A host that has not responded past the threshold can be ignored
                # TODO: This should probably go in backbone master land
                continue

            # TODO: There is a potential case here where we want to clear out remnant
            # roles (pf9apps) from a newly/unauthorized hosts.

            # assignment to _unauthorized_* dicts is atomic. There is no need
            # for a lock here.
            # See http://effbot.org/pyfaq/what-kinds-of-global-value-mutation-are-thread-safe.htm
            log.info('adding new host %s to unauthorized hosts' % unauth_host)
            _unauthorized_hosts[host] = unauth_host
            _unauthorized_host_status_time[host] = status_time

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
                    _unauthorized_hosts.pop(host, None)
                    _unauthorized_host_status_time.pop(host, None)
                    self.notifier.publish_notification('delete', 'host', host)
                    continue

            if host in authorized_hosts and authorized_hosts[host]['responding']:
                log.info('Host %s being marked as not responding', host)
                self.db_handle.mark_host_state(host, responding=False)
                self.notifier.publish_notification('change', 'host', host)

    def _update_role_status(self, host_id, host):
        if _authorized_host_role_status.get(host_id) != host['status']:
            _authorized_host_role_status[host_id] = host['status']
            self.notifier.publish_notification('change', 'host', host_id)

    def _process_existing_hosts(self, host_ids, authorized_hosts):
        """
        Process hosts that are reported by backbone and is also tracked in our state
        :param list host_ids: list of host ids
        :param dict authorized_hosts: details of the authorized hosts
        """
        for host in host_ids:
            try:
                host_info = call_remote_service('%s/v1/hosts/%s' %
                                                (self.bbone_endpoint, host))
            except BBMasterNotFound:
                log.exception('Querying backbone for %s failed', host)
                # TODO: Should we return instead of continuing here?
                continue

            status_time = datetime.datetime.strptime(host_info['timestamp'],
                                                     "%Y-%m-%d %H:%M:%S.%f")
            if host in authorized_hosts:
                # host is in authorized list
                responding = self._responding_within_threshold(status_time)
                if authorized_hosts[host]['responding'] != responding:
                    # If host status is responding and is marked as not
                    # responding, tag it as responding. And vice versa
                    self.db_handle.mark_host_state(host, responding=responding)
                    self.notifier.publish_notification('change', 'host', host)
                    log.info('Marking %s as %s responding, status time: %s',
                             host, '' if responding else 'not', host_info['timestamp'])
                if not responding:
                    # If not responding, nothing more to do
                    continue

                self._update_role_status(host, host_info)

                host_status = host_info['status']
                # Active hosts but we need to change the configuration
                try:
                    if host_status not in ('ok', 'retrying', 'converging'):
                        # Failed or missing status, nothing to do right now
                        continue

                    cfg_key = 'apps' if host_status == 'ok' else 'desired_apps'
                    # if host_status is 'ok'
                    # Check if app status in the DB is same as the app config
                    # in the result
                    # if host_status is 'retrying' or 'converging'
                    # Check if desired app status in result is same as app status
                    # in DB
                    # TODO: Cross check if this is intended design
                    expected_cfg = substitute_host_id(
                        authorized_hosts[host]['apps_config'],
                        host)
                    role_settings = authorized_hosts[host]['role_settings']
                    roles = self.rolemgr.db_handler.query_roles()
                    _update_custom_role_settings(expected_cfg, json.loads(role_settings), roles)
                    if not is_satisfied_by(expected_cfg, host_info[cfg_key]):
                        log.debug('Pushing new configuration for %s, config: %s. '
                                  'Expected config %s', host, host_info['apps'],
                                  expected_cfg)
                        self.rolemgr.push_configuration(host, expected_cfg,
                                                        needs_hostid_subst=False)
                except (BBMasterNotFound, HostConfigFailed):
                    log.exception('Backbone request for %s failed', host)
                    continue
            else:
                # assignment to _unauthorized_* dicts is atomic. There is no need
                # for a lock here.
                # See http://effbot.org/pyfaq/what-kinds-of-global-value-mutation-are-thread-safe.htm
                _unauthorized_host_status_time[host] = status_time
                # TODO: Is there a need to update the unauthorized hosts with the data
                # returned from bbone?

    def _cleanup_unauthorized_hosts(self):
        """
        Cleanup unauthorized hosts that have not reported a status message
        within the status time.
        """
        cleanup_hosts = []
        with _host_lock:
            for id in _unauthorized_hosts.iterkeys():
                if not self._responding_within_threshold(_unauthorized_host_status_time[id]):
                    # Maintain a list of hosts that are past the threshold
                    cleanup_hosts.append(id)

            if cleanup_hosts:
                log.warn("Unauthorized hosts that are being removed: %s", cleanup_hosts)

            for id in cleanup_hosts:
                _unauthorized_hosts.pop(id, None)
                _unauthorized_host_status_time.pop(id, None)
                self.notifier.publish_notification('delete', 'host', id)

    def process_hosts(self):
        """
        Routine to query bbone for host info and process it
        """
        try:
            bbone_ids = set(call_remote_service('%s/v1/hosts/ids' %
                                                self.bbone_endpoint))
        except BBMasterNotFound:
            log.exception('Querying backbone for hosts failed')
        else:
            # Get authorized host ids and unauthorized host ids and store it
            # in all_ids
            authorized_hosts = self.db_handle.query_host_and_app_details()
            all_ids = set(authorized_hosts.keys() + _unauthorized_hosts.keys())
            new_ids = bbone_ids - all_ids
            del_ids = all_ids - bbone_ids
            exist_ids = all_ids & bbone_ids

            # Process hosts that are newly reported from backbone
            self._process_new_hosts(new_ids)
            # Process hosts that backbone claims are not present anymore(?)
            self._process_absent_hosts(del_ids, authorized_hosts)
            # Deal with changes to existing hosts
            self._process_existing_hosts(exist_ids, authorized_hosts)
            # Cleanup older unauthorized hosts
            self._cleanup_unauthorized_hosts()

    def run(self):
        """
        Main poller routine
        """
        log.debug('start backbone poll routine')
        while (True):
            # Get the host ids that backbone is aware of
            try:
                self.process_hosts()
            except:
                # Ensure that this poller will never go down.
                # Log and continue
                log.exception('Poller encountered an error')
            # Sleep for the poll interval
            time.sleep(self.poll_interval)


class ResMgrPf9Provider(ResMgrProvider):
    """
    Implementation of the ResMgrProvider interface
    """
    def __init__(self, config_file):
        """
        Constructor
        :param str config_file: Path to configuration file for resource manager
        """
        # Load the config file as well as the global config file.
        config = ConfigParser.ConfigParser()
        config.read(config_file)
        global_cfg_file = config.get('resmgr', 'global_config_file')
        config.read(global_cfg_file)

        self.res_mgr_db = ResMgrDB(config)
        self.host_inventory_mgr = HostInventoryMgr(config, self.res_mgr_db)
        self.roles_mgr = RolesMgr(config, self.res_mgr_db)
        notifier.init(log, config)

        rabbit_username = config.get('amqp', 'username')
        rabbit_password = config.get('amqp', 'password')
        self._rabbit_mgmt_cl = rabbit.RabbitMgmtClient(rabbit_username,
                                                       rabbit_password)
        self.setup_rabbit_credentials()
        self.bb_url = config.get('backbone', 'endpointURI')

        # Setup a thread to poll backbone state regularly to detect changes to
        # hosts.
        self.bbone_poller = BbonePoller(config, self.res_mgr_db,
                                        self.roles_mgr, notifier)
        t = threading.Thread(target=self.bbone_poller.run)
        t.daemon = True
        t.start()

    def setup_rabbit_credentials(self):
        """
        Sync the rabbit_credentials table with the actual RabbitMQ list
        of users.
        """
        log.info('Adding RabbitMQ users from the rabbit_credentials table')

        # Maps roles to rabbit permissions
        rabbit_permissions_map = {}
        for role in self.res_mgr_db.query_roles():
            rabbit_permissions_map[role.rolename] = json.loads(role.rabbit_permissions)

        for credential in self.res_mgr_db.query_rabbit_credentials():
            rabbit_permissions = rabbit_permissions_map[credential.rolename]
            self._rabbit_mgmt_cl.create_user(credential.userid,
                                             credential.password)
            self._rabbit_mgmt_cl.set_permissions(credential.userid,
                                                 rabbit_permissions['config'],
                                                 rabbit_permissions['write'],
                                                 rabbit_permissions['read'])

    def request_support_bundle(self, host_id):
        url = "%s/v1/hosts/%s/support/bundle" % (self.bb_url, host_id)
        try:
            r = requests.post(url)
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

    def get_all_roles(self):
        """
        Returns information about all known roles
        :return: dictionary of roles and their information
        :rtype: dict
        """
        return self.roles_mgr.get_all_roles()

    def get_role(self, role_name):
        """
        Returns all information about a role
        :param str role_name: Name of the role
        :return: dictionary of the role information
        :rtype: dict
        """
        return self.roles_mgr.get_role(role_name)

    def get_all_hosts(self):
        """
        Returns information about all known hosts
        :return: dictionary of hosts and their information
        :rtype: dict
        """
        return self.host_inventory_mgr.get_all_hosts()

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
        if host_inst['roles']:
            log.debug('Removing roles and state entries in the database for %s',
                      host_id)
            _authorized_host_role_status[host_id] = None
            self.res_mgr_db.update_roles_for_host(host_id, roles=[])
            credentials_to_delete = self.res_mgr_db.query_rabbit_credentials(host_id=host_id)
            # The rabbit_credentials entry associated with this host will also
            # be removed due to cascading deletes.
            self.res_mgr_db.delete_host(host_id)
            notifier.publish_notification('delete', 'host', host_id)
            self.delete_rabbit_credentials(credentials_to_delete)
            log.debug('Sending request to backbone to remove all roles from %s',
                      host_id)
            self.roles_mgr.push_configuration(host_id, app_info={},
                                              needs_rabbit_subst=False)

    def delete_rabbit_credentials(self, credentials):
        for credential in credentials:
            try:
                self._rabbit_mgmt_cl.delete_user(credential.userid)
            except:
                log.error('Failed to clean up RabbitMQ user: %s',
                          credential.userid)

    def random_string_generator(self, len=16):
        return "".join([random.choice(string.ascii_letters + string.digits) for _ in
                xrange(len)])

    def create_rabbit_credentials(self, host_id, role_name):
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
            rabbit_user = self.random_string_generator()
            rabbit_password = self.random_string_generator()
        self._rabbit_mgmt_cl.create_user(rabbit_user, rabbit_password)
        active_role = self.res_mgr_db.query_role(role_name)
        permissions = json.loads(active_role.rabbit_permissions)
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

    def add_role(self, host_id, role_name, host_settings):
        """
        Add a role to a particular host
        :param str host_id: ID of the host
        :param str role_name: Name of the role
        :param dict host_settings: Custom settings for the host
            if host_settings is None, all of the host's custom settings
            will be replaced with the defaults
        :raises RoleNotFound: if the role is not present
        :raises HostNotFound: if the host is not present
        :raises HostConfigFailed: if setting the configuration fails or times out
        :raises BBMasterNotFound: if communication to the backbone fails
        """
        log.info('Assigning role %s to %s with host settings %s',
                 role_name, host_id, host_settings)
        active_role_in_db = self.res_mgr_db.query_role(role_name)
        if not active_role_in_db:
            log.error('Role %s is not found in list of active roles', role_name)
            raise RoleNotFound(role_name)

        host_inst = self.host_inventory_mgr.get_host(host_id)
        if not host_inst:
            log.error('Host %s is not a recognized host', host_id)
            raise HostNotFound(host_id)

        host_roles = self.res_mgr_db.query_host(host_id, fetch_role_ids=True)
        if host_roles and active_role_in_db.id in host_roles['roles']:
            log.info('Role %s is already assigned to %s', role_name, host_id)
            return

        initially_inactive = host_inst['state'] == RState.inactive
        host_inst['roles'].append(role_name)
        _authorized_host_role_status[host_id] = None

        if initially_inactive:
            assert host_id in _unauthorized_hosts
            host_inst['state'] = RState.activating
            notifier.publish_notification('change', 'host', host_id)

        try:
            # 1. Record the role addition state in the DB
            # 2. Publish change notification
            # 3. Push the new configuration to the host
            # Push configuration to bbone is idempotent, so we will end up with
            # a converged state eventually.
            log.debug('Updating host %s state after %s role association',
                      host_id, role_name)
            rabbit_user, rabbit_password = self.create_rabbit_credentials(host_id, role_name)
            self.res_mgr_db.insert_update_host(host_id, host_inst['info'], role_name, host_settings)
            self.res_mgr_db.associate_role_to_host(host_id, role_name)
            self.res_mgr_db.associate_rabbit_credentials_to_host(host_id,
                                                                 role_name,
                                                                 rabbit_user,
                                                                 rabbit_password)

            with _host_lock:
                # Once added to the DB, remove it from the unauthorized host dict
                _unauthorized_hosts.pop(host_id, None)
                _unauthorized_host_status_time.pop(host_id, None)

            # Rely on the role config values set in the DB to send to bbmaster
            host_details = self.res_mgr_db.query_host_and_app_details(host_id)
            app_info = host_details[host_id]['apps_config']
            role_settings = json.loads(host_details[host_id]['role_settings'])
            roles = self.roles_mgr.db_handler.query_roles()
            _update_custom_role_settings(app_info, role_settings, roles)
            log.info('Sending request to backbone to add role %s to %s with config %s',
                     role_name, host_id, app_info)
            self.roles_mgr.push_configuration(host_id, app_info)
        except:
            if initially_inactive:
                host_inst['state'] = RState.inactive
            try:
                self._rabbit_mgmt_cl.delete_user(rabbit_user)
            except:
                log.warn('Failed to clean up rabbit user %s after failure while '
                         'adding role %s to host %s' % (rabbit_user, role_name, host_id))
            raise

        notifier.publish_notification('change', 'host', host_id)

    def delete_role(self, host_id, role_name):
        """
        Disassociates a role from a host.
        :param str host_id: ID of the host
        :param str role_name: Name of the role
        :raises RoleNotFound: if the role is not present
        :raises HostNotFound: if the host is not present
        :raises HostConfigFailed: if setting the configuration fails or times out
        :raises BBMasterNotFound: if communication to the backbone fails
        """
        log.info('Removing role %s from %s', role_name, host_id)
        if host_id in _unauthorized_hosts:
            log.warn('Host %s is classified as unauthorized host. Nothing '
                     'to delete', host_id)
            return
        active_role_in_db = self.res_mgr_db.query_role(role_name)
        if not active_role_in_db:
            log.error('Role %s is not found in list of active roles', role_name)
            raise RoleNotFound(role_name)

        host_inst = self.host_inventory_mgr.get_host(host_id)
        if not host_inst:
            log.error('Host %s is not a recognized host', host_id)
            raise HostNotFound(host_id)

        if role_name not in host_inst['roles']:
            log.warn('Role %s is not assigned to %s', role_name, host_id)
            return

        host_inst['roles'].remove(role_name)

        # 1. Record the role removal state in the DB
        # 2. Publish change notification
        # 3. Push the new configuration to the host
        # Push configuration to bbone is idempotent, so we will end up with
        # a converged state eventually.
        log.debug('Clearing role %s for host %s in DB', role_name, host_id)
        credentials_to_delete = self.res_mgr_db.query_rabbit_credentials(
                host_id=host_id,
                rolename=role_name)
        if len(credentials_to_delete) != 1:
            msg = ('Invalid number of rabbit credentials for host %s and role %s'
                   % (host_id, role_name))
            log.error(msg)
            raise RabbitCredentialsConfigureError(msg)
        self.res_mgr_db.remove_role_from_host(host_id, role_name)
        self.delete_rabbit_credentials(credentials_to_delete)
        notifier.publish_notification('change', 'host', host_id)
        # TODO: Think about if there is a case to remove this host from the
        # database. If removing role from db, the role_status should be changed.
        # See IAAS-649

        log.debug('Sending request to backbone to remove role %s from %s',
                 role_name, host_id)
        host_details = self.res_mgr_db.query_host_and_app_details(host_id)
        self.roles_mgr.push_configuration(host_id,
                             host_details[host_id]['apps_config'])

    def get_custom_settings(self, host_id, role_name):
        return self.res_mgr_db.get_custom_settings(host_id, role_name)


def get_provider(config_file):
    return ResMgrPf9Provider(config_file)
