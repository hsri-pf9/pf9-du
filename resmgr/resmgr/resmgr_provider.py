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
    def get_roles(self, id_list=[]):
        pass

    @abstractmethod
    def get_resources(self, id_list=[]):
        pass

    @abstractmethod
    def add_role(self, res_id, role_id):
        pass

    @abstractmethod
    def delete_role(self, res_id, role_id):
        pass


