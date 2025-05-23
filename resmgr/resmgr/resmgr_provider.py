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
    def get_role(self, role_name):
        """
        Returns information about a particular role in active state
        :param role_name: Name of the role
        :rtype: dict
        """
        pass

    @abstractmethod
    def get_role_with_version(self, role_name, version):
        """
        Returns information about a particular role with given version
        :param role_name: Name of the role
        :param version: version of the role
        :rtype: dict
        """
        pass


    @abstractmethod
    def mark_role_version_active(self, role_name, version, active):
        """
        Marks a role with given version as active
        :param role_name: Name of the role
        :param version: version of the role
        :param active: Flag indicating if the role is to marked as active.
        """
        pass


    @abstractmethod
    def create_role(self, role_info):
        """
        Creates a role with incoming role information and stores
        this role in the database.
        :param role_info : JSON with role information.
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
    def get_all_hosts(self, role_settings=False):
        """
        Returns information about all known hosts
        :rtype: dict
        """
        pass

    @abstractmethod
    def add_role(self, host_id, role_id, version, host_settings):
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

