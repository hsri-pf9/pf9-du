# Copyright 2019 Platform9 Systems Inc.
# All Rights reserved


__author__ = 'Platform9'
import pecan
from pecan.rest import RestController

class VersionsController(RestController):
    @pecan.expose('json')
    def get(self):
        return {'v1': 'supported, current', 'v2': 'experimental'}
