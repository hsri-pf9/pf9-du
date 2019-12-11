# Copyright 2019 Platform9 Systems Inc.
# All Rights reserved


__author__ = 'Platform9'
from resmgr.controllers.resmgr_controller import HostsController
from resmgr.controllers.resmgr_controller import HostsControllerV2
from resmgr.controllers.resmgr_controller import RolesController
from resmgr.controllers.resmgr_controller import ServicesController
from resmgr.controllers.versions_controller import VersionsController
from resmgr.controllers.metrics_controller import MetricsController

class V1Controller(object):
    roles = RolesController()
    hosts = HostsController()
    services = ServicesController()

class V2Controller(V1Controller):
    hosts = HostsControllerV2()

class RootController(object):
    v1 = V1Controller()
    v2 = V2Controller()
    versions = VersionsController()
    metrics = MetricsController()
