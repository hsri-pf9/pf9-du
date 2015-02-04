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
        return self.msg


class RoleNotFound(ResMgrException):
    def __init__(self, val):
        super(RoleNotFound, self).__init__('Role %s not found' % val)


class RoleExists(ResMgrException):
    def __init__(self, roleKey, resKey):
        super(RoleExists, self).__init__('Role %s already associated with resource %s'
                                         %(roleKey, resKey))

class HostNotFound(ResMgrException):
    def __init__(self, val):
        super(HostNotFound, self).__init__('Host %s not found' % val)

class BBMasterNotFound(ResMgrException):
    def __init__(self, val):
        super(BBMasterNotFound, self).__init__('Backbone master unreachable %s' % val)

class HostConfigFailed(ResMgrException):
    def __init__(self, reason):
        super(HostConfigFailed, self).__init__('Role configuration failed: %s'% reason)

class SupportRequestFailed(ResMgrException):
    def __init__(self, reason):
        super(SupportRequestFailed, self).__init__('Support request failed: %s' % reason)

class SupportCommandRequestFailed(ResMgrException):
    def __init__(self, reason):
        super(SupportCommandRequestFailed, self).__init__('Support command request failed: %s' % reason)

class RabbitCredentialsConfigureError(ResMgrException):
    def __init__(self, reason):
        super(RabbitCredentialsConfigureError, self).__init__('Failed to get rabbit credentials: %s' % reason)
