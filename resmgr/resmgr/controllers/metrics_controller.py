# Copyright 2019 Platform9 Systems Inc.
# All Rights reserved


__author__ = 'Platform9'
import pecan
from pecan.rest import RestController
from prometheus_client import generate_latest


class MetricsController(RestController):
    @pecan.expose(content_type='text/plain')
    def get(self):
        return generate_latest()
