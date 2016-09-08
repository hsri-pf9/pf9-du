# Copyright (c) 2016 Platform9 Systems Inc. All Rights Reserved.

"""
Auth events for 'test-role' loaded into tests that subclass
dbtestcase.py::DbTestCase
"""
import mock

on_auth = mock.Mock()
on_deauth = mock.Mock()
on_auth_converged = mock.Mock()
on_deauth_converged = mock.Mock()
