# Copyright 2014 Platform9 Systems Inc.
# All Rights reserved


__author__ = 'Platform9'

"""
This module defines the interface of Resource Manager Provider
"""

from abc import ABCMeta, abstractmethod

class RState(object):
    inactive = "inactive"
    active = "active"
    activating = "activating"

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
    def get_resource(self, resource_id):
        """
        Returns detailed information about a particular resource
        :param resource_id: ID of the resource
        :rtype: dict
        """
        pass


    @abstractmethod
    def get_all_resources(self):
        """
        Returns information about all known resources
        :rtype: dict
        """
        pass

    @abstractmethod
    def add_role(self, res_id, role_id):
        """
        Adds a role to a resource
        :param res_id: ID of the resource
        :param role_id: ID of the role
        """
        pass

    @abstractmethod
    def delete_role(self, res_id, role_id):
        """
        Disassociates a role from a resource
        :param res_id: ID of the resource
        :param role_id: ID of the role
        :return:
        """
        pass

