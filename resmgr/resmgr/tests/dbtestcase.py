# Copyright (c) 2016 Platform9 Systems Inc. All Rights Reserved.

import copy
import logging
import mock
import os
import tempfile
import unittest

from ConfigParser import ConfigParser
from resmgr import dbutils
from resmgr import migrate_db
from StringIO import StringIO

logging.basicConfig(level=logging.DEBUG)

LOG = logging.getLogger(__name__)

THISDIR = os.path.abspath(os.path.dirname(__file__))

RESMGR_CONF = \
"""
[DEFAULT]
DU_FQDN = test_du_fqdn

[database]
sqlconnectURI = sqlite:///%(sqlite_temp_file)s

[pf9-cindervolume]
auth_user = cinder
auth_pass = ks_pass
db_pass = db_pass
auth_tenant_name = services

[pf9-ceilometer]
auth_user = ceilometer
auth_pass = ks_pass
auth_tenant_name = services

[test-role]
conf1 = conf1_value
param1 = param1_value
param2 = param2_value

[backbone]
endpointURI = http://fake
requestWaitPeriod = 30
requestTimeout = 30
pollInterval = 30

[amqp]
username = rabbituser
password = rabbitpass

[resmgr]
defaultNonResponsiveHostThreshold = 30
convergingNonResponsiveHostThreshold = 30

"""

# FIXME - Evidently, the app name must be 'in' the role name in order for
# customizable parameters to be substituted in. Thus here both the app
# the role are called 'test-role'.
# See resmgr_provider_pf9:_update_custom_role_settings
TEST_ROLE = {
    "test-role": {
        "1.0": {
            "role_name": "test-role",
            "display_name": "Test Role",
            "description": "This is a test role.",
            "customizable_settings": {
                "customizable_key": {
                    "path": "config/test_conf/customizable_section",
                    "default": "default value for customizable_key"
                },
            },
            "rabbit_permissions": {
                "config": "^(glance|openstack|reply_.*)$",
                "write": "^(glance|openstack|reply_.*)$",
                "read": "^(reply_.*)$"
            },
            "role_version": "1.0",
            "config": {
                "test-role": {
                     "version": "1.0",
                     "service_states": {"test-service": "true"},
                     "url": "%(download_protocol)s://%(host_relative_amqp_fqdn)s:"
                            "%(download_port)s/private/test-role-1.0.rpm",
                     "du_config": {
                        "auth_events": {
                            "type": "python",
                            "module_path": os.path.join(THISDIR,
                                                        'test_auth_events.py'),
                            "params": {
                                "param1": "%(test-role.param1)s",
                                "param2": "%(test-role.param2)s"
                            }
                        }
                     },
                     "config": {
                         "test_conf": {
                             "DEFAULT": {
                                 "conf1": "%(test-role.conf1)s"
                             },
                             "customizable_section": {}
                         }
                    }
                }
            }
        }
    }
}

TEST_HOST = {
    'id': '1234',
    'details': {
        'hostname': 'test-host.platform9.sys',
        'arch': 'x86_64',
        'os_family': 'Linux',
        'os_info': 'centos'
    }
}

class DbTestCase(unittest.TestCase):

    def setUp(self):
        self._patches = []

        # load the role from above + second one instead of a file
        self._load_roles_from_files = \
                self._patchobj(dbutils.ResMgrDB, '_load_roles_from_files')
        test_roles = copy.deepcopy(TEST_ROLE)
        test_roles['test-role-2'] = copy.deepcopy(TEST_ROLE['test-role'])
        test_roles['test-role-2']['1.0']['role_name'] = 'test-roles-2'
        self._load_roles_from_files.return_value = test_roles

        # create a tempfile for sqlite
        sqlite_temp_file = tempfile.mkstemp(prefix='resmgr-testdb-',
                                            suffix='.sqlite')
        os.close(sqlite_temp_file[0])
        self._sqlite_temp_file = sqlite_temp_file[1]

        # resmgr config
        resmgr_config = RESMGR_CONF % {'sqlite_temp_file':
                                       self._sqlite_temp_file}
        self._cfg = ConfigParser()
        self._cfg.readfp(StringIO(resmgr_config))

        # init the db and get an instance of ResMgrDB
        get_resmgr_db_url = \
                self._patchfun('resmgr.migrate_db._get_resmgr_db_url')
        get_resmgr_db_url.return_value = \
                self._cfg.get('database', 'sqlconnectURI')
        migrate_db.migrate_db()

        # ^#@%ing global variables
        dbutils.engineHandle = None

    def tearDown(self):
        self._unpatchall()
        os.unlink(self._sqlite_temp_file)

    def _patchfun(self, name):
        patch = mock.patch(name)
        self._patches.append(patch)
        return patch.start()

    def _patchobj(self, cls, member):
        patch = mock.patch.object(cls, member)
        self._patches.append(patch)
        return patch.start()

    def _unpatchall(self):
        for patch in self._patches:
            patch.stop()
