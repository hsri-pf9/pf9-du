# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'Platform9'

"""
Root level controllers for the backbone master webservice. Provides the root and
the version controller for the webservice requests.
"""

from bbmaster.controllers.hosts_controller import HostsController

class V1Controller(object):
    '''
    Version 1 of the controller
    '''
    hosts = HostsController()

class RootController(object):
    '''
    Root controller class for the backbone master REST API
    '''
    v1 = V1Controller()
