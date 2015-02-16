# Copyright 2013 Platform9 Systems Inc.
# All Rights Reserved.

"""
This module is a mock implementation of the backbone provider interface.
"""

from bbone_provider import bbone_provider

class bbone_provider_memory(bbone_provider):
    """Mock provider class. Works off mock data loaded in memory"""

    def __init__(self):
        self.hosts = {}
        self.desired_apps = {}
        self.host_agents = {}
        self.hosts_with_queues = set()

    def get_host_ids(self):
        """
        Return all host ids.
        :return: list of all the host IDs
        :rtype: list
        """
        return self.hosts.keys()

    def get_hosts(self, id_list=[], show_comms=False):
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

    def set_host_agent_config(self, host_id, agent_config):
        """
        Updates the host agent config state for a particular host
        :param str host_id: ID of the host
        :param dict agent_config: Configuration of the host agent that needs
        to be updated.
        """
        self.host_agents[host_id] = agent_config


    def set_host_agent(self, host_id, agent_data):
        """
        Update the host agent on a particular host
        :param str host_id: ID of the host
        :param dict agent_data: Information about the new host agent. This includes
        URL, name and version for the host agent rpm.
        """
        if host_id not in self.host_agents:
            # Set up an empty config in the dict if it is a
            # new host id that we are seeing
            self.set_host_agent_config(host_id, {})

    def get_host_agent(self, host_id):
        """
        Returns the host agent properties
        :param str host_id: Host's id
        """
        return self.host_agents.get(host_id) \
            if host_id in self.host_agents else {}
