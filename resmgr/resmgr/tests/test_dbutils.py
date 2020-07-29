# Copyright (c) 2016 Platform9 Systems Inc. All Rights Reserved.

import copy
import logging
import os

from resmgr import dbutils
from resmgr import role_states
from resmgr.tests.dbtestcase import DbTestCase, TEST_HOST, TEST_ROLE
from resmgr.dbutils import SafeValue

logging.basicConfig(level=logging.DEBUG)
LOG = logging.getLogger(__name__)

THISDIR = os.path.abspath(os.path.dirname(__file__))

class TestDb(DbTestCase):

    def setUp(self):
        super(TestDb, self).setUp()
        self._db = dbutils.ResMgrDB(self._cfg)
        self._db_cipher_key = \
            self._patchobj(SafeValue, 'get_resmgr_db_cipher_key')
        self._db_cipher_key.return_value = "wjFGEGAmdEaaaaaa"

    def tearDown(self):
        super(TestDb, self).tearDown()

    def _associate_role(self, rolename, version,
                        customizable_params,
                        rabbit_user, rabbit_pass):
        self._db.insert_update_host(TEST_HOST['id'],
                                    TEST_HOST['details'],
                                    rolename,
                                    version,
                                    customizable_params)
        self._db.associate_role_to_host(TEST_HOST['id'], rolename, version)
        self._db.associate_rabbit_credentials_to_host(TEST_HOST['id'],
                                                      rolename,
                                                      rabbit_user,
                                                      rabbit_pass)
        result = self._db._get_rabbit_credential_params(TEST_HOST['id'], rolename)
        self.assertEqual(rabbit_user, result['rabbit_userid'])
        self.assertEqual(rabbit_pass, result['rabbit_password'])

    def _add_host_with_customizable_role(self, apply_roleversion,
                                         applied_roleversion, customvalues):
        self._associate_role('test-role', apply_roleversion,
                             customvalues,
                             'rabbit', 'p@55wd')
        host_id = TEST_HOST['id']
        deets = self._db.query_host_and_app_details()
        self.assertEqual(1, len(deets))
        self.assertEqual({'test-role': customvalues},
                          deets[host_id]['role_settings'])
        self.assertEqual(applied_roleversion,
                          deets[host_id]['role_details'][0].version)

    def test_add_host_with_customizable_role(self):
        self._add_host_with_customizable_role(None, '1.0',
                                {'customizable_key': 'customizable_value'})
        self._add_host_with_customizable_role('0.5', '0.5',
                                {'customizable_key': 'customizable_value_0.5'})

    def _add_role(self, apply_roleversion, applied_roleversion, customvalues):
        self._associate_role('test-role', apply_roleversion,
                             customvalues,
                             'rabbit', 'p@55wd')
        host_id = TEST_HOST['id']
        roleid = 'test-role_%s' % applied_roleversion
        deets = self._db.query_host_and_app_details()
        self.assertEqual(1, len(deets))
        self.assertEqual(role_states.NOT_APPLIED,
                          deets[host_id]['role_states'][roleid])
        self.assertTrue('test-role' in deets[host_id][
            'apps_config_including_deauthed_roles'])

        attrs_with_rolenames = self._db.query_host(host_id, fetch_role_ids=False)
        self.assertEqual(host_id, attrs_with_rolenames['id'])
        self.assertEqual(1, len(attrs_with_rolenames['roles']))
        self.assertEqual('test-role', attrs_with_rolenames['roles'][0])

        attrs_with_role_ids = self._db.query_host(host_id, fetch_role_ids=True)
        self.assertEqual(host_id, attrs_with_role_ids['id'])
        self.assertEqual(1, len(attrs_with_role_ids['roles']))
        self.assertEqual(roleid, attrs_with_role_ids['roles'][0])

        # check another api
        roles = self._db.query_roles_for_host(host_id)
        self.assertEqual(1, len(roles))
        self.assertEqual(roleid, roles[0].id)

    def test_add_role(self):
        self._add_role(None, '1.0', {'customizable_key': 'customizable_value'})
        self._add_role('0.5', '0.5', {'customizable_key': 'customizable_value_0.5'})

    def test_upgrade_role(self):

        # setup host with test-role 1.0 fully applied
        self._associate_role('test-role', None,
                             {'customizable_key': 'customizable_value'},
                             'rabbit', 'p@55wd')
        self._associate_role('test-role-2', None,
                             {'customizable_key': 'customizable_value'},
                             'rabbit', 'p@55wd')
        host_id = TEST_HOST['id']

        deets = self._db.query_host_and_app_details()
        self.assertEqual(1, len(deets))
        self.assertEqual(role_states.NOT_APPLIED,
                          deets[host_id]['role_states']['test-role_1.0'])
        self.assertTrue('test-role' in deets[host_id][
            'apps_config_including_deauthed_roles'])
        result = self._db.advance_role_state(host_id, 'test-role',
                                             role_states.NOT_APPLIED,
                                             role_states.START_APPLY)
        self.assertTrue(result)
        deets = self._db.query_host_and_app_details()
        self.assertEqual(role_states.START_APPLY,
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

        # there should be five roles, with 2.0 as the active one for test-role.
        roles = self._db.query_roles(active_only=False)
        self.assertEqual(5, len(roles))
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
                                    None,
                                    {'customizable_key': 'customizable_value'})
        self._db.associate_role_to_host(host_id, 'test-role')
        deets = self._db.query_host_and_app_details()
        self.assertEqual(2, len(deets[host_id]['role_states']))
        self.assertEqual(role_states.START_APPLY,
                          deets[host_id]['role_states']['test-role_2.0'])

    def _remove_role(self, apply_roleversion, applied_roleversion, customvalues):
        self._associate_role('test-role', apply_roleversion,
                             customvalues,
                             'rabbit', 'p@55wd')
        host_id = TEST_HOST['id']
        role_id = 'test-role_%s' % applied_roleversion
        deets = self._db.query_host_and_app_details()
        self.assertEqual(1, len(deets))
        self.assertEqual(role_states.NOT_APPLIED,
                          deets[host_id]['role_states'][role_id])
        self.assertTrue('test-role' in deets['1234'][
            'apps_config_including_deauthed_roles'])

        self._db.remove_role_from_host(host_id, 'test-role')
        deets = self._db.query_host_and_app_details()
        self.assertEqual(1, len(deets))
        self.assertEqual({}, deets[host_id]['apps_config'])
        self.assertEqual({}, deets[host_id]['role_states'])

    def test_remove_role(self):
        self._remove_role(None, '1.0', {'customizable_key': 'customizable_value'})
        self._remove_role('0.5', '0.5', {'customizable_key': 'customizable_value_0.5'})

    def test_update_host_info(self):
        host_id = TEST_HOST['id']

        # Add host with mock host info
        self._associate_role('test-role', None,
                             {'customizable_key': 'customizable_value'},
                             'rabbit', 'p@55wd')

        host_details = self._db.query_host_and_app_details()
        self.assertEqual(host_details[host_id]['hostosinfo'], 'centos')

        # Update host OS info
        good_host_info = {
            'hostarch': 'i386',
            'hostosinfo': 'LFS 8.4'
        }
        result = self._db.update_host_info(host_id, good_host_info)
        self.assertFalse(result)

        host_details = self._db.query_host_and_app_details()
        self.assertEqual(1, len(host_details))
        self.assertEqual(host_details[host_id]['hostarch'], 'i386')
        self.assertEqual(host_details[host_id]['hostosinfo'], 'LFS 8.4')

        # Test updating nonexistent database column
        bad_host_info = {'nonexistent_column': 'Garbage data'}
        result = self._db.update_host_info(host_id, bad_host_info)
        self.assertFalse(result)

        host_details = self._db.query_host_and_app_details()
        self.assertEqual(1, len(host_details))

        with self.assertRaises(KeyError):
            host_details[host_id]['nonexistent_column']

    def test_update_role_state(self):
        self._associate_role('test-role', None,
                             {'customizable_key': 'customizable_value'},
                             'rabbit', 'p@55wd')
        host_id = TEST_HOST['id']
        result = self._db.advance_role_state(host_id, 'test-role',
                                             role_states.APPLIED,
                                             role_states.START_EDIT)
        self.assertFalse(result)
        deets = self._db.query_host_and_app_details()
        self.assertEqual(1, len(deets))
        self.assertEqual(role_states.NOT_APPLIED,
                          deets[host_id]['role_states']['test-role_1.0'])

        result = self._db.advance_role_state(host_id, 'test-role',
                                             role_states.NOT_APPLIED,
                                             role_states.START_APPLY)
        self.assertTrue(result)
        deets = self._db.query_host_and_app_details()
        self.assertEqual(role_states.START_APPLY,
                          deets[host_id]['role_states']['test-role_1.0'])

    def test_move_new_state(self):
        self._associate_role('test-role', None,
                             {'customizable_key': 'customizable_value'},
                             'rabbit', 'p@55wd')
        host_id = TEST_HOST['id']
        result = self._db.advance_role_state(host_id, 'test-role',
                                             role_states.NOT_APPLIED,
                                             role_states.START_APPLY)
        self.assertTrue(result)

        with self._db.move_new_state(host_id, 'test-role',
                                     role_states.START_APPLY,
                                     role_states.PRE_AUTH,
                                     role_states.NOT_APPLIED):
            LOG.info('Successfully executed the body!')
        deets = self._db.query_host_and_app_details()
        self.assertEqual(role_states.PRE_AUTH,
                          deets[host_id]['role_states']['test-role_1.0'])

    def test_move_new_state_fail(self):
        self._associate_role('test-role', None,
                             {'customizable_key': 'customizable_value'},
                             'rabbit', 'p@55wd')
        host_id = TEST_HOST['id']
        result = self._db.advance_role_state(host_id, 'test-role',
                                             role_states.NOT_APPLIED,
                                             role_states.START_APPLY)
        self.assertTrue(result)

        with self.assertRaises(RuntimeError):
            with self._db.move_new_state(host_id, 'test-role',
                                         role_states.START_APPLY,
                                         role_states.PRE_AUTH,
                                         role_states.NOT_APPLIED):
                raise RuntimeError('Failed to execute the body')
        deets = self._db.query_host_and_app_details()
        self.assertEqual(role_states.NOT_APPLIED,
                          deets[host_id]['role_states']['test-role_1.0'])

    def test_get_all_role_associations(self):
        self._associate_role('test-role', None,
                             {'customizable_key': 'customizable_value'},
                             'rabbit', 'p@55wd')
        self._associate_role('test-role-2', None,
                             {'customizable_key': 'customizable_value'},
                             'rabbit', 'p@55wd')
        host_id = TEST_HOST['id']
        assocs = self._db.get_all_role_associations(host_id)
        self.assertTrue(assocs)
        self.assertEqual(['test-role', 'test-role-2'],
                          sorted([a.role.rolename for a in assocs]))
