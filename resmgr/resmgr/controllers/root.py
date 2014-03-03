# Copyright 2014 Platform9 Systems Inc.
# All Rights reserved


__author__ = 'Platform9'

from resmgr_controller import RolesController, ResourcesController

class V1Controller(object):
    roles = RolesController()
    resources = ResourcesController()

class RootController(object):
    v1 = V1Controller()
