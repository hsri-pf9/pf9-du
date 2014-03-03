# Copyright 2013 Platform9 Systems Inc.
# All Rights Reserved.

"""
This module is a mock implementation of the backbone provider interface.
"""

from bbone_provider import bbone_provider
import copy

class bbone_provider_memory(bbone_provider):
    """Mock provider class. Works off mock data loaded in memory"""

    def __init__(self):
        self.hosts = {}
        self.desired_apps = {}

    def load_test_data(self, test_data):
        self.hosts = test_data

    def get_host_ids(self):
        """
        Return all host ids.
        :return: list of all the host IDs
        :rtype: list
        """
        return self.hosts.keys()

    def get_hosts(self, id_list=[]):
        if not id_list:
            id_list = [host_id for host_id in self.hosts]
        return [self.hosts[id] for id in id_list if id in self.hosts]

    def set_host_apps(self, id, apps_config):
        """
        Update the desired app config of the host.
        """
        if id not in self.hosts:
            self.hosts[id] = {
                'host_id': id,
                'status': 'missing'
            }
        self.desired_apps[id] = apps_config

provider = bbone_provider_memory()
