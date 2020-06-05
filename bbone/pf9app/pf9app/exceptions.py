# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'leb'

class Pf9Exception(Exception):
    pass

class NotDownloaded(Pf9Exception):
    pass

class AlreadyInstalled(Pf9Exception):
    pass

class NotInstalled(Pf9Exception):
    pass

class DownloadFailed(Pf9Exception):
    pass

class ServiceCtrlError(Pf9Exception):
    pass

class ConfigOperationError(Pf9Exception):
    pass

class UpdateOperationFailed(Pf9Exception):
    pass

class RemoveOperationFailed(Pf9Exception):
    pass

class InstallOperationFailed(Pf9Exception):
    pass

class PackageFileNameNotSpecified(Pf9Exception):
    pass

class UrlNotSpecified(Pf9Exception):
    pass

class InvalidSupportedDistro(Pf9Exception):
    pass
