# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights Reserved.

class BackboneException(Exception):
    pass

class HostNotFound(BackboneException):
    pass

class Pf9FirmwareAppsError(BackboneException):
    pass