# Copyright 2018 Platform9 Systems Inc. All Rights Reserved

# pylint: disable=too-few-public-methods

import base64
import json
import logging
import os
import re
import requests
import threading

from six.moves.configparser import DuplicateSectionError

from firkinize.configstore.consul import Consul

LOG = logging.getLogger(__name__)

class ConsulUnavailable(Exception):
    pass

class ConsulRoles(object):
    def __init__(self, config, db):
        """
        Create a consul watch on the resource manager role configuration.
        :param config: A ConfigParser object into which we can save role
            configuration parameters.
        :param db: a ResMgrDB object into which we can register roles.

        Role config json docs are loaded from consul at
        customers/<id>/regions/<id>/roles/<rolename>/<roleversion>/config

        Parameters are loaded from
        customers/<id>/regions/<id>/roles/params/<rolename>/<paramname>.

        Parameters show up in the resmgr configuration as rolename.paramname,
        similar to the way we load ini files from /etc/pf9/resmgr_roles/conf.d
        and end up with 'flattened' params like section.param = value
        """
        self._config = config
        self._db = db
        try:
            customer_id = os.environ['CUSTOMER_ID']
            region_id = os.environ['REGION_ID']
            consul_url = os.environ.get('CONFIG_URL', 'http://localhost:8500')
            consul_token = os.environ.get('CONSUL_HTTP_TOKEN', None)
            self._prefix = 'customers/%s/regions/%s/roles' % (customer_id, region_id)
            self._consul = Consul(consul_url, consul_token)
            self._watch = self._consul.prefix_watch(self._prefix, self._callback)
            self._watch_thread = threading.Thread(target=self._watch.run)
            self._watch_thread.daemon = True
            self._pending_role_updates = set()
            LOG.info('Initialized consul watch for role changes on %s',
                     consul_url)
        except KeyError as e:
            raise ConsulUnavailable('Missing environment configuration for '
                'consul watcher, role updates from consul are not available: '
                '%s' % e)
        except requests.RequestException as e:
            raise ConsulUnavailable('Failed to contact consul at %s, role '
                'updates from consul are not available: %s' % (consul_url, e))
        self._key_callbacks = [
            # prefix/rolename/version/config = config json
            (re.compile(r'%s/([^\/]*)/([^\/]*)/config' % self._prefix),
             self._on_config_change),
            # prefix/params/rolename/paramname = value
            (re.compile(r'%s/params/([^\/]*)/([^\/]*)' % self._prefix),
             self._on_params_change)
        ]
        self._active_roles = {}

    def startwatch(self):
        LOG.info('Starting consul role watch')
        self._watch_thread.start()

    def _callback(self, updates):
        for update in updates:
            for rex, callback in self._key_callbacks:
                m = rex.match(update['Key'])
                if m:
                    value = base64.b64decode(update['Value'])
                    callback(m.groups(), value)

    def _on_config_change(self, key_elems, value):
        rolename = key_elems[0]
        version = key_elems[1]
        LOG.info("Fetching active version for role: %s", rolename)
        key = '/'.join([self._prefix, rolename, 'active_version'])
        active_version = None
        try:
            active_version = self._consul.kv_get(key)
            LOG.info("Fetched active version:%s for role: %s",
                     active_version, rolename)
        except Exception:
            LOG.warn("Could not fetch active version for role: %s", rolename)
        LOG.info('Updating role %s, version %s', rolename, version)
        config = json.loads(value.decode())
        if active_version and version == active_version:
            self._active_roles[rolename] = {
                'active_version': active_version,
                'config': config
            }
        try:
            self._db.save_role_in_db(rolename, version, config)
            LOG.info('Saved %s role, version %s in the database',
                     rolename, version)
            if rolename in self._active_roles and \
                    version != self._active_roles[rolename]['active_version']:
                active_version = self._active_roles[rolename]['active_version']
                active_config = self._active_roles[rolename]['config']
                LOG.info('Current version: %s does not match active version: '
                         '%s. Re-adding active version role.', version,
                         active_version)
                self._db.save_role_in_db(rolename, active_version,
                                         active_config)
        except KeyError:
            LOG.exception('Role %s failed validation. Queueing for later in '
                          'case a new parameter shows up in consul', rolename)
            self._pending_role_updates.add((key_elems, value))

    def _on_params_change(self, key_elems, value):
        rolename = key_elems[0]
        param_name = key_elems[1]
        LOG.info('Updating role param %s for role %s', param_name, rolename)
        try:
            self._config.add_section(rolename)
            LOG.info('Created config section %s', rolename)
        except DuplicateSectionError:
            LOG.info('Config section %s already exists', rolename)
        value = value.decode()
        self._config.set(rolename, param_name, value)

        # The new param may make it possible to save a role that failed to
        # validate earlier. Let's try to save the pending adds again. If one
        # fails, it will be re-added to self._pending_role_updates.
        pending = self._pending_role_updates
        self._pending_role_updates = set()
        LOG.info('Attempting to add pending role updates...')
        for update in pending:
            self._on_config_change(*update)
