# Copyright (c) 2016 Platform9 Systems Inc. All Rights Reserved.

"""
Auth events for 'test-role' loaded into tests that subclass
dbtestcase.py::DbTestCase
"""
import mock
import os
import sys

on_auth = mock.Mock()
on_deauth = mock.Mock()
on_auth_converged = mock.Mock()
on_deauth_converged = mock.Mock()

# The tests set an environment variable to select an event that should
# fail. If it's set, add the exception side_effect.
fail_auth_event = os.environ.get('PF9_RESMGR_FAIL_EVENT', None)
if fail_auth_event:
    this_module = sys.modules[__name__]
    getattr(this_module, fail_auth_event).side_effect = \
            RuntimeError('%s has failed!', fail_auth_event)
