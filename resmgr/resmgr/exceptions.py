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

class MalformedRequest(ResMgrException):
    def __init__(self, errorCode, errorMsg):
        super(MalformedRequest, self).__init__('Malformed request')
        self.errorCode = errorCode
        self.errorMsg = errorMsg

class RoleNotFound(ResMgrException):
    def __init__(self, val):
        super(RoleNotFound, self).__init__('Role %s not found' % val)

class RoleVersionNotFound(ResMgrException):
    def __init__(self, name, version):
        super(RoleVersionNotFound, self).__init__(
            'Role %s, version %s not found' % (name, version))

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

class CertRefreshRequestFailed(ResMgrException):
    def __init__(self, reason):
        super(CertRefreshRequestFailed, self).__init__('Host cert refresh request failed: %s' % reason)

class RabbitCredentialsConfigureError(ResMgrException):
    def __init__(self, reason):
        super(RabbitCredentialsConfigureError, self).__init__('Failed to get rabbit credentials: %s' % reason)

class DuConfigError(ResMgrException):
    def __init__(self, reason):
        super(DuConfigError, self).__init__(
                'Failed to run on-DU authorization task: %s' % reason)

class ServiceNotFound(ResMgrException):
    def __init__(self, val):
        super(ServiceNotFound, self).__init__('Service %s not found' % val)

class ServiceConfigFailed(ResMgrException):
    def __init__(self, reason):
        super(ServiceConfigFailed, self).__init__(
            'Failed to set service configuration: %s' % reason)

class RoleUpdateConflict(ResMgrException):
    def __init__(self, reason):
        super(RoleUpdateConflict, self).__init__(
            'Role cannot be updated in the current state: %s' % reason)

class HostDown(ResMgrException):
    def __init__(self, reason):
        super(HostDown, self).__init__('Host is down: %s' % reason)

class ResmgrConfigError(ResMgrException):
    def __init__(self, reason):
        super(ResmgrConfigError, self).__init__('Failed to get resmgr config: %s' % reason)

class RoleKeyMalformed(ResMgrException):
    def __init__(self, reason):
        super(RoleKeyMalformed, self).__init__('Incomplete role info: %s' % reason)

class RoleVersionExists(ResMgrException):
    def __init__(self, reason):
        super(RoleVersionExists, self).__init__(
            'Duplicate role: %s' % reason)

class RoleInactiveNotAllowed(ResMgrException):
    def __init__(self, reason):
        super(RoleInactiveNotAllowed, self).__init__(
            'Marking role inactive not allowed: %s' % reason)
