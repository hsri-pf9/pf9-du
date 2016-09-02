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
print 'THISDIR = ' + THISDIR

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
"""

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
                "test-role-app-1": {
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

class TestDb(unittest.TestCase):

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
        self._db = dbutils.ResMgrDB(self._cfg)

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

    def test_add_host_with_customizable_role(self):
        self._db.insert_update_host(TEST_HOST['id'],
                                    TEST_HOST['details'],
                                    'test-role',
                                    {'customizable_key': 'customizable_value'})
        host_id = TEST_HOST['id']
        deets = self._db.query_host_and_app_details()
        self.assertEquals(1, len(deets))
        self.assertEquals({'test-role': {'customizable_key':
                                         'customizable_value'}},
                          deets[host_id]['role_settings'])

    def test_add_role(self):
        self._db.insert_update_host(TEST_HOST['id'],
                                    TEST_HOST['details'],
                                    'test-role',
                                    {'customizable_key': 'customizable_value'})
        host_id = TEST_HOST['id']
        self._db.associate_role_to_host(host_id, 'test-role')
        deets = self._db.query_host_and_app_details()
        self.assertEquals(1, len(deets))
        self.assertEquals('un-applied',
                          deets[host_id]['role_states']['test-role_1.0'])
        self.assertTrue('test-role-app-1' in deets[host_id]['apps_config'])

        attrs_with_rolenames = self._db.query_host(host_id, fetch_role_ids=False)
        self.assertEquals(host_id, attrs_with_rolenames['id'])
        self.assertEquals(1, len(attrs_with_rolenames['roles']))
        self.assertEquals('test-role', attrs_with_rolenames['roles'][0])

        attrs_with_role_ids = self._db.query_host(host_id, fetch_role_ids=True)
        self.assertEquals(host_id, attrs_with_role_ids['id'])
        self.assertEquals(1, len(attrs_with_role_ids['roles']))
        self.assertEquals('test-role_1.0', attrs_with_role_ids['roles'][0])

        # check another api
        roles = self._db.query_roles_for_host(host_id)
        self.assertEquals(1, len(roles))
        self.assertEquals('test-role_1.0', roles[0].id)

    def test_upgrade_role(self):

        # setup host with test-role 1.0 fully applied
        self._db.insert_update_host(TEST_HOST['id'],
                                    TEST_HOST['details'],
                                    'test-role',
                                    {'customizable_key': 'customizable_value'})
        host_id = TEST_HOST['id']

        self._db.associate_role_to_host(host_id, 'test-role')
        self._db.associate_role_to_host(host_id, 'test-role-2')
        deets = self._db.query_host_and_app_details()
        self.assertEquals(1, len(deets))
        self.assertEquals('un-applied',
                          deets[host_id]['role_states']['test-role_1.0'])
        self.assertTrue('test-role-app-1' in deets[host_id]['apps_config'])
        result = self._db.advance_role_state(host_id, 'test-role_1.0',
                                             'un-applied', 'applied')
        deets = self._db.query_host_and_app_details()
        self.assertEquals('applied',
                          deets[host_id]['role_states']['test-role_1.0'])

        # new version of test-role:
        new_role = {
            'test-role': {
                '2.0': copy.deepcopy(TEST_ROLE['test-role']['1.0'])
            }
        }
        new_role['test-role']['2.0']['role_version'] = '2.0'
        new_role['test-role']['2.0']['config']['test-role-app-1']['version'] = '2.0'
        self._load_roles_from_files.return_value = new_role
        self._db.setup_roles()

        # there should be three roles, with 2.0 as the active one for test-role.
        roles = self._db.query_roles(active_only=False)
        self.assertEquals(3, len(roles))
        old = None
        new = None
        other = None
        for role in roles:
            if role.rolename == 'test-role-2':
                other = role
            elif role.version == '1.0':
                old = role
            elif role.version == '2.0':
                new = role
        self.assertTrue(old)
        self.assertFalse(old.active)
        self.assertTrue(new)
        self.assertTrue(new.active)
        self.assertTrue(other)
        self.assertTrue(other.active)

        # do role association for test-role. Role should be upgraded,
        # current_state should still be 'applied'.
        self._db.insert_update_host(TEST_HOST['id'],
                                    TEST_HOST['details'],
                                    'test-role',
                                    {'customizable_key': 'customizable_value'})
        self._db.associate_role_to_host(host_id, 'test-role')
        deets = self._db.query_host_and_app_details()
        self.assertEquals(2, len(deets[host_id]['role_states']))
        self.assertEquals('applied',
                          deets[host_id]['role_states']['test-role_2.0'])

    def test_remove_role(self):
        self._db.insert_update_host(TEST_HOST['id'],
                                    TEST_HOST['details'],
                                    'test-role',
                                    {'customizable_key': 'customizable_value'})
        host_id = TEST_HOST['id']
        self._db.associate_role_to_host(host_id, 'test-role')

        deets = self._db.query_host_and_app_details()
        self.assertEquals(1, len(deets))
        self.assertEquals('un-applied',
                          deets[host_id]['role_states']['test-role_1.0'])
        self.assertTrue('test-role-app-1' in deets['1234']['apps_config'])

        self._db.remove_role_from_host(host_id, 'test-role')
        deets = self._db.query_host_and_app_details()
        self.assertEquals(1, len(deets))
        self.assertEquals({}, deets[host_id]['apps_config'])
        self.assertEquals({}, deets[host_id]['role_states'])

    def test_remove_all_roles(self):
        self._db.insert_update_host(TEST_HOST['id'],
                                    TEST_HOST['details'],
                                    'test-role',
                                    {'customizable_key': 'customizable_value'})
        host_id = TEST_HOST['id']
        self._db.associate_role_to_host(host_id, 'test-role')
        deets = self._db.query_host_and_app_details()
        self.assertEquals(1, len(deets))
        self.assertEquals('un-applied',
                          deets[host_id]['role_states']['test-role_1.0'])
        self.assertTrue('test-role-app-1' in deets['1234']['apps_config'])

        self._db.update_roles_for_host(host_id, [])
        deets = self._db.query_host_and_app_details()
        self.assertEquals(1, len(deets))
        self.assertEquals({}, deets[host_id]['apps_config'])
        self.assertEquals({}, deets[host_id]['role_states'])

    def test_update_role_state(self):
        host_id = TEST_HOST['id']
        self._db.insert_update_host(TEST_HOST['id'],
                                    TEST_HOST['details'],
                                    'test-role',
                                    {'customizable_key': 'customizable_value'})
        self._db.associate_role_to_host(host_id, 'test-role')
        result = self._db.advance_role_state(host_id, 'test-role_1.0',
                                             'applied', 'start-apply')
        self.assertFalse(result)
        deets = self._db.query_host_and_app_details()
        self.assertEquals(1, len(deets))
        self.assertEquals('un-applied',
                          deets[host_id]['role_states']['test-role_1.0'])

        result = self._db.advance_role_state(host_id, 'test-role_1.0',
                                             'un-applied', 'start-apply')
        self.assertTrue(result)
        deets = self._db.query_host_and_app_details()
        self.assertEquals('start-apply',
                          deets[host_id]['role_states']['test-role_1.0'])

