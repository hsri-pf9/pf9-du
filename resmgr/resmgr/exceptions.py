# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved

__author__ = "Platform9"

"""
Exceptions for Resource Manager
"""

class ResMgrException(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __repr__(self):
        return msg


class RoleNotFound(ResMgrException):
    def __init__(self, val):
        super(RoleNotFound, self).__init__('Role %s not found' % val)


class RoleExists(ResMgrException):
    def __init__(self, roleKey, resKey):
        super(RoleExists, self).__init__('Role %s already associated with resource %s'
                                         %(roleKey, resKey))

class ResourceNotFound(ResMgrException):
    def __init__(self, val):
        super(ResourceNotFound, self).__init__('Resource %s not found' % val)

class BBMasterNotFound(ResMgrException):
    def __init__(self, val):
        super(BBMasterNotFound, self).__init__('Backbone master unreachable %s' % val)

class ResConfigFailed(ResMgrException):
    def __init__(self, reason):
        super(ResConfigFailed, self).__init__('Role configuration failed: %s'% reason)

