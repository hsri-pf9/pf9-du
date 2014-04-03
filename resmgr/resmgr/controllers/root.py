# Copyright 2014 Platform9 Systems Inc.
# All Rights reserved


__author__ = 'Platform9'

from resmgr_controller import RolesController, HostsController

class V1Controller(object):
    roles = RolesController()
    hosts = HostsController()

class RootController(object):
    v1 = V1Controller()
