# Copyright 2013 Platform9 Systems Inc.
# All Rights Reserved.

"""
This module is a mock implementation of the backbone provider interface.
"""

from .bbone_provider_memory import bbone_provider_memory

class bbone_provider_mock(bbone_provider_memory):
    """
    Mock provider class. Works off mock data loaded in memory. To be used for
    test purposes.
    """

    def __init__(self):
        super(bbone_provider_mock, self).__init__()

    def load_test_data(self, test_data):
        self.hosts = test_data

    def set_host_apps(self, id, apps_config):
        """
        Update the app config of the host.
        """
        super(bbone_provider_mock, self).set_host_apps(id, apps_config)
        if id in self.hosts and self.hosts[id]['status'] != 'missing':
            # Set the apps only if the id exists and is not missing
            self.hosts[id]['apps'] = apps_config

provider = bbone_provider_mock()
