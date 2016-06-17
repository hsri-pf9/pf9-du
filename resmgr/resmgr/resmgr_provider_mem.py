# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved

__author__ = "Platform9"

"""
This module is mock implementation of resource manager provider interface
"""

from resmgr_provider import ResMgrProvider
from exceptions import RoleNotFound, HostNotFound
import notifier
import logging
import json
from ConfigParser import ConfigParser
from os import environ

class ResMgrMemProvider(ResMgrProvider):

    def __init__(self, conf_file):
        """ Mock memory based provider """
        self.hosts = None
        self.roles = None
        self.publish_notifications = False
        if 'PUBLISH_CHANGES' in environ:
            self._configure_change_publisher()

    def _configure_change_publisher(self):
        config = ConfigParser()
        config.add_section('amqp')
        config.set('amqp', 'host', 'rabbitmq')
        config.set('amqp', 'username', 'guest')
        config.set('amqp', 'password', 'm1llenn1umFalc0n')
        log = logging
        log.basicConfig(level=logging.INFO)
        notifier.init(log, config)
        self.publish_notifications = True

    def _refresh_data(self):
        with open('resmgr/tests/mock_data.json') as json_file:
            try:
                d = json.load(json_file)
                self._load_data(d['mock_resources'], d['mock_roles'])
            except (ValueError, KeyError, TypeError) as e:
                logging.error('Malformed data: %s', json_file)

    def _load_data(self, hosts, roles):
        if not hosts or not roles:
            return

        # Simple check
        if not self.hosts:
            self.hosts = hosts
            self.roles = roles
            return

        # If the dictonary keys changed from memory-loaded values, update
        if set(self.hosts.keys()) != set(hosts.keys()) or \
                set(self.roles.keys()) != set(roles.keys()):
            self.hosts = hosts
            self.roles = roles

    def get_all_roles(self):
        return self._get_roles()

    def get_role(self, role_id):
        return self._get_roles([role_id])

    def _get_roles(self, id_list=[]):
        #prereq
        self._refresh_data()

        all_roles = self.roles

        if not id_list:
            return all_roles

        sub_roles = dict((key, val) for key, val in all_roles.iteritems() \
                             if key in id_list)

        ## TODO: error handling
        return sub_roles

    def get_all_hosts(self):
        return self._get_hosts()

    def get_host(self, host_id):
        host = self._get_hosts([host_id])
        return host[host_id] if host else {}


    def delete_host(self, host_id):
        self._refresh_data()

        if host_id not in self.hosts.keys():
            raise HostNotFound(host_id)

        del self.hosts[host_id]
        return


    def _get_hosts(self, id_list=[]):
        #prereq
        self._refresh_data()

        if not id_list:
            return self.hosts

        sub_hosts = dict((key, val) for key, val in self.hosts.iteritems()
                         if key in id_list)

        ## TODO: error handling
        return sub_hosts

    def _get_host_roles(self, host_id, role_id):

        if host_id not in self.hosts.keys():
            raise HostNotFound(host_id)

        if role_id not in self.roles.keys():
            raise RoleNotFound(role_id)

        return self.hosts[host_id], self.roles[role_id]

    def add_role(self, host_id, role_id, host_settings):
        #prereq
        self._refresh_data()

        host, role = self._get_host_roles(host_id, role_id)

        # Mock host configuration
        host['roles'].append(role_id)

        if self.publish_notifications:
            notifier.publish_notification('change', 'host', host_id)

    def delete_role(self, host_id, role_id):
        #prereq
        self._refresh_data()

        host, role = self._get_host_roles(host_id, role_id)

        # TODO: error handling
        if not host['roles'] or role_id not in host['roles']:
            return

        host['roles'].remove(role_id)

        if self.publish_notifications:
            notifier.publish_notification('change', 'host', host_id)

def get_provider(config_file):
    return ResMgrMemProvider(config_file)
