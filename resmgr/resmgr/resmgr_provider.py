# Copyright 2014 Platform9 Systems Inc.
# All Rights reserved


__author__ = 'Platform9'

"""
This module defines the interface of Resource Manager Provider
"""

from abc import ABCMeta, abstractmethod

class ResMgrProvider(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def get_all_roles(self):
        """
        Returns information of all known roles
        :rtype: dict
        """
        pass

    @abstractmethod
    def get_role(self, role_id):
        """
        Returns information about a particular role
        :param role_id: ID of the role
        :rtype: dict
        """
        pass


    @abstractmethod
    def get_host(self, host_id):
        """
        Returns detailed information about a particular host
        :param host_id: ID of the host
        :rtype: dict
        """
        pass

    @abstractmethod
    def delete_host(self, host_id):
        """
        Delete a host
        :param host_id: ID
        :return:
        """
        pass

    @abstractmethod
    def get_all_hosts(self):
        """
        Returns information about all known hosts
        :rtype: dict
        """
        pass

    @abstractmethod
    def add_role(self, host_id, role_id, host_settings):
        """
        Adds a role to a host
        :param host_id: ID of the host
        :param role_id: ID of the role
        """
        pass

    @abstractmethod
    def delete_role(self, host_id, role_id):
        """
        Disassociates a role from a host
        :param host_id: ID of the host
        :param role_id: ID of the role
        :return:
        """
        pass

