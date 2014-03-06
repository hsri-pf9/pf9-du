# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved

__author__ = "Platform9"

"""
This module is mock implementation of resource manager provider interface
"""

from resmgr_provider import ResMgrProvider, RState
from exceptions import RoleNotFound, ResourceNotFound
import logging
import json

class ResMgrMemProvider(ResMgrProvider):

    def __init__(self, conf_file):
        """ Mock memory based provider """
        self.res = None
        self.roles = None


    def _refresh_data(self):
        with open('resmgr/tests/mock_data.json') as json_file:
            try:
                d = json.load(json_file)
                self._load_data(d['mock_resources'], d['mock_roles'])
            except (ValueError, KeyError, TypeError) as e:
                logging.error('Malformed data: %s', json_file)

    def _load_data(self, res, roles):
        if not res or not roles:
            return

        # Simple check
        if not self.res:
            self.res = res
            self.roles = roles
            return

        # If the dictonary keys changed from memory-loaded values, update
        if set(self.res.keys()) != set(res.keys()) or \
                set(self.roles.keys()) != set(roles.keys()):
            self.res = res
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

    def get_all_resources(self):
        return self._get_resources()

    def get_resource(self, resource_id):
        return self._get_resources([resource_id])

    def _get_resources(self, id_list=[]):
        #prereq
        self._refresh_data()

        if not id_list:
            return self.res

        sub_res = dict((key, val) for key, val in self.res.iteritems() \
                           if key in id_list)

        ## TODO: error handling
        return sub_res

    def _get_res_roles(self, res_id, role_id):

        if res_id not in self.res.keys():
            raise ResourceNotFound(res_id)

        if role_id not in self.roles.keys():
            raise RoleNotFound(role_id)

        return self.res[res_id], self.roles[role_id]

    def add_role(self, res_id, role_id):
        #prereq
        self._refresh_data()

        res, role = self._get_res_roles(res_id, role_id)


        #TODO:Right now, this mapping is one to one to keep status consistent.
        # Revisit
        if res['state'] != RState.inactive:
            return

        # Mock resource configuration
        res['state'] = RState.activating
        res['roles'].append(role_id)

        res['state'] = RState.active

    def delete_role(self, res_id, role_id):
        #prereq
        self._refresh_data()

        res, role = self._get_res_roles(res_id, role_id)

        # TODO: error handling
        if res['state'] != RState.active or \
                not res['roles'] or role_id not in res['roles']:
            return

        res['roles'].remove(role_id)

        if not res['roles']:
            res['state'] = RState.inactive


def get_provider(config_file):
    return ResMgrMemProvider(config_file)