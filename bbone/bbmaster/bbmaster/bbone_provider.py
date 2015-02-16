# Copyright 2013 Platform9 Systems Inc.
# All Rights Reserved.

"""
This module defines the interface to a backbone provider.
"""

from abc import ABCMeta, abstractmethod

class bbone_provider:
    __metaclass__ = ABCMeta

    @abstractmethod
    def get_host_ids(self):
        """
        Returns the ids of all known hosts
        """
        pass

    @abstractmethod
    def get_hosts(self, id_list=[], show_comms=False):
        """
        Returns a list of host descriptors corresponding to the specified
        id list. If the list is empty, all host descriptors are returned.
        :param id_list: list of host ids
        :param show_comms: whether to show pf9-comms in app configurations
        :rtype: list
        """
        pass

    @abstractmethod
    def set_host_apps(self, id, apps_config):
        """
        Set the desired app configuration for the specified host.
        :param str id: the host's id
        """
        pass

    @abstractmethod
    def get_host_agent(self, id):
        """
        Returns the host agent properties
        :param str id: Host's id
        """
        pass

    @abstractmethod
    def set_host_agent(self, id, agent_data):
        """
        Updates the host agent on the host to the agent as specified by
        the agent url
        :param str id: ID of the host
        :param dict agent_data: Information about the new host agent. This includes
        URL, name and version for the host agent rpm.
        """
        pass
