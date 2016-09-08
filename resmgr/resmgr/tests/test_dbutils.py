# Copyright (c) 2016 Platform9 Systems Inc. All Rights Reserved.

import copy
import logging
import os

from resmgr import dbutils
from resmgr import role_states
from resmgr.tests.dbtestcase import DbTestCase, TEST_HOST, TEST_ROLE

logging.basicConfig(level=logging.DEBUG)
LOG = logging.getLogger(__name__)

THISDIR = os.path.abspath(os.path.dirname(__file__))

class TestDb(DbTestCase):

    def setUp(self):
        super(TestDb, self).setUp()
        self._db = dbutils.ResMgrDB(self._cfg)

    def tearDown(self):
        super(TestDb, self).tearDown()

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
        self.assertEquals(role_states.NOT_APPLIED,
                          deets[host_id]['role_states']['test-role_1.0'])
        self.assertTrue('test-role' in deets[host_id]['apps_config'])

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
        self.assertEquals(role_states.NOT_APPLIED,
                          deets[host_id]['role_states']['test-role_1.0'])
        self.assertTrue('test-role' in deets[host_id]['apps_config'])
        result = self._db.advance_role_state(host_id, 'test-role_1.0',
                                             role_states.NOT_APPLIED,
                                             role_states.START_APPLY)
        self.assertTrue(result)
        deets = self._db.query_host_and_app_details()
        self.assertEquals(role_states.START_APPLY,
                          deets[host_id]['role_states']['test-role_1.0'])

        # new version of test-role:
        new_role = {
            'test-role': {
                '2.0': copy.deepcopy(TEST_ROLE['test-role']['1.0'])
            }
        }
        new_role['test-role']['2.0']['role_version'] = '2.0'
        new_role['test-role']['2.0']['config']['test-role']['version'] = '2.0'
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
        # current_state should still be 'start-apply'.
        self._db.insert_update_host(TEST_HOST['id'],
                                    TEST_HOST['details'],
                                    'test-role',
                                    {'customizable_key': 'customizable_value'})
        self._db.associate_role_to_host(host_id, 'test-role')
        deets = self._db.query_host_and_app_details()
        self.assertEquals(2, len(deets[host_id]['role_states']))
        self.assertEquals(role_states.START_APPLY,
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
        self.assertEquals(role_states.NOT_APPLIED,
                          deets[host_id]['role_states']['test-role_1.0'])
        self.assertTrue('test-role' in deets['1234']['apps_config'])

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
        self.assertEquals(role_states.NOT_APPLIED,
                          deets[host_id]['role_states']['test-role_1.0'])
        self.assertTrue('test-role' in deets['1234']['apps_config'])

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
                                             role_states.APPLIED,
                                             role_states.START_EDIT)
        self.assertFalse(result)
        deets = self._db.query_host_and_app_details()
        self.assertEquals(1, len(deets))
        self.assertEquals(role_states.NOT_APPLIED,
                          deets[host_id]['role_states']['test-role_1.0'])

        result = self._db.advance_role_state(host_id, 'test-role_1.0',
                                             role_states.NOT_APPLIED,
                                             role_states.START_APPLY)
        self.assertTrue(result)
        deets = self._db.query_host_and_app_details()
        self.assertEquals(role_states.START_APPLY,
                          deets[host_id]['role_states']['test-role_1.0'])

