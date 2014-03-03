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
    def get_hosts(self, id_list=[]):
        """
        Returns a list of host descriptors corresponding to the specified
        id list. If the list is empty, all host descriptors are returned.
        :param id_list: list of host ids
        :rtype: list
        """
        pass

    @abstractmethod
    def set_host_apps(self, id, apps_config):
        """
        Set the desired app configuration for the specified host.
        :id: the host's id
        """
        pass





