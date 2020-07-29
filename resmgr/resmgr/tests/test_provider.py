# Copyright (c) 2016 Platform9 Systems Inc. All Rights Reserved.

# pylint: disable=protected-access, too-many-instance-attributes
# pylint: disable=too-few-public-methods, too-many-public-methods

import copy
import json
import logging
import mock
import os
import random
import requests
import shutil
import sys
import tempfile
import threading
import time

from datetime import datetime
from rabbit import RabbitMgmtClient
from resmgr import resmgr_provider_pf9
from resmgr import role_states
from resmgr.exceptions import DuConfigError, RoleUpdateConflict, HostDown
from resmgr.resmgr_provider_pf9 import ResMgrPf9Provider, BbonePoller
from resmgr.resmgr_provider_pf9 import log as provider_logger
from resmgr.tests.dbtestcase import DbTestCase
from resmgr.tests.dbtestcase import TEST_HOST, TEST_ROLE
from resmgr.dbutils import SafeValue

logging.basicConfig(level=logging.DEBUG)
LOG = logging.getLogger(__name__)

THISDIR = os.path.abspath(os.path.dirname(__file__))

BBONE_IDS = set([TEST_HOST['id']])
BBONE_HOST = {
    'extensions': {
        'interfaces': {
            'data': {
                'iface_ip': {'eth0': '10.4.253.124'},
                'ovs_bridges': []
            },
            'status': 'ok'
        },
        'ip_address': {
            'data': ['10.4.253.124'],
            'status': 'ok'
        },
        'volumes_present': {
            'data': [
                {'free': '0', 'name': 'ubuntu12-vg', 'size': '16.76g'}
            ],
            'status': 'ok'
        }
    },
    'host_agent': {'status': 'running', 'version': '2.2.0-1463.5ae865b'},
    'host_id': TEST_HOST['id'],
    'hypervisor_info': {'hypervisor_type': 'kvm'},
    'info': {
        'arch': 'x86_64',
        'hostname': 'ubuntu12.platform9.sys',
        'os_family': 'Linux',
        'os_info': 'Ubuntu 12.04 precise'
    },
    'status': 'ok',
    'timestamp': '2016-09-08 23:16:40.398866',
    'timestamp_on_du': '2016-09-08 23:16:40.786359'
}

MISSING_BBONE_HOST = {
    'host_id': TEST_HOST['id'],
    'status': 'missing',
    'timestamp': '1970-01-01 00:00:00.000000',
    'timestamp_on_du': '1970-01-01 00:00:00.000000'
}

RABBIT_USER = 'bugs'
RABBIT_PASS = 'whatsupdoc'
RABBIT_URL = 'rabbit://%s:%s@localhost:5673/' % (RABBIT_USER, RABBIT_PASS)

BBONE_APPS = {
    "test-role": {
        "version": "1.0",
        "service_states": {"test-service": "true"},
        "config": {
            "test_conf": {
                "DEFAULT": {
                    "conf1": "conf1_value",
                    "rabbit_user": RABBIT_USER,
                    "rabbit_password": RABBIT_PASS,
                    "rabbit_transport_url": RABBIT_URL,
                    "legacy_rabbit_transport_url": RABBIT_URL,
                    "endpoint_spec": "http://something/%(project_id)s"
                },
                "customizable_section": {
                    "customizable_key": "default value for customizable_key"
                }
            }
        }
    }
}

BBONE_PUSH = copy.deepcopy(BBONE_APPS)
BBONE_PUSH['test-role']['url'] = \
    "%(download_protocol)s://%(host_relative_amqp_fqdn)s:" \
    "%(download_port)s/private/test-role-1.0.rpm"

# Contains both test-role and test-role-2
BBONE_COMBINED_PUSH = copy.deepcopy(BBONE_PUSH)
BBONE_COMBINED_PUSH['test-role-2'] = copy.deepcopy(BBONE_COMBINED_PUSH['test-role'])


class match_dict_to_jsonified(object):
    """
    __eq__ is true when the other object is a json string representing
    the wrapped dictionary. Used to test actual json string bodies sent to
    requests against an expected dictionary.
    see http://www.voidspace.org.uk/python/mock/examples.html#more-complex-argument-matching
    """
    def __init__(self, dictionary):
        self._dict = dictionary
        self._other = None
    def __eq__(self, jsonified):
        other = json.loads(jsonified)
        return self._dict == other
    def __repr__(self):
        return str(self._dict)

class TestProvider(DbTestCase):

    def setUp(self):
        super(TestProvider, self).setUp()
        self._load_provider_config = \
                self._patchobj(ResMgrPf9Provider, '_load_config')
        self._load_provider_config.return_value = self._cfg

        # FIXME: verify notifier calls
        self._patchfun('notifier.init')
        self._patchfun('notifier.publish_notification')

        self._create_rabbit_user = self._patchobj(RabbitMgmtClient,
                                                  'create_user')
        self._delete_rabbit_user = self._patchobj(RabbitMgmtClient,
                                                  'delete_user')
        self._patchobj(RabbitMgmtClient, 'set_permissions')

        self._random_rabbit_creds = \
            self._patchobj(ResMgrPf9Provider, '_random_rabbit_creds')
        self._random_rabbit_creds.return_value = (RABBIT_USER, RABBIT_PASS)

        # FIXME: check service config
        self._patchobj(ResMgrPf9Provider, 'run_service_config')

        self._db_cipher_key = \
            self._patchobj(SafeValue, 'get_resmgr_db_cipher_key')
        self._db_cipher_key.return_value = "wjFGEGAmdEaaaaaa"

        self.tempdirpath = tempfile.mkdtemp()
        os.environ['prometheus_multiproc_dir'] = self.tempdirpath
        os.environ['PF9SRESDK_SERVICE_NAME'] = 'pf9-resmgr'

        # don't start the BbonePoller in a thread. The tests will call
        # process_hosts directly when appropriate.
        self._real_thread_start = threading.Thread.start
        self._patchobj(threading.Thread, 'start')

        # reset the provider global state
        self._reset_provider_global_state()

        # now we can create the provider.
        self._provider = ResMgrPf9Provider('not a real config file')

        # shorthand member objects
        self._inventory = self._provider.host_inventory_mgr
        self._bbone = self._provider.bbone_poller
        self._db = self._provider.res_mgr_db

        # now add an unauthorized host to the in-memory dictionaries
        self._get_backbone_host_ids = \
            self._patchobj(BbonePoller, '_get_backbone_host_ids')
        self._get_backbone_host_ids.return_value = BBONE_IDS
        self._get_backbone_host = \
            self._patchobj(BbonePoller, '_get_backbone_host')
        self._get_backbone_host.return_value = self._unauthed_host()
        self._responding_within_threshold = \
            self._patchobj(BbonePoller, '_responding_within_threshold')
        self._responding_within_threshold.return_value = True
        self._bbone.process_hosts()

        # RolesMgr uses requests.put to send new config to a host through
        # bbmaster. Intercept that and respond with 200
        self._requests_put = self._patchfun('requests.put')
        self._requests_put.return_value = self._plain_http_response(200)

        # used to control failures in the test_auth_events late-loaded module
        os.environ.pop('PF9_RESMGR_FAIL_EVENT', None)

    def tearDown(self):
        super(TestProvider, self).tearDown()
        shutil.rmtree(self.tempdirpath)

    @staticmethod
    def _reset_provider_global_state():
        resmgr_provider_pf9._unauthorized_hosts = {}
        resmgr_provider_pf9._unauthorized_host_status_time = {}
        resmgr_provider_pf9._unauthorized_host_status_time_on_du = {}
        resmgr_provider_pf9._authorized_host_role_status = {}
        resmgr_provider_pf9._hosts_hypervisor_info = {}
        resmgr_provider_pf9._hosts_extension_data = {}
        resmgr_provider_pf9._hosts_message_data = {}
        resmgr_provider_pf9._host_lock = threading.Lock()
        resmgr_provider_pf9._role_delete_lock = threading.RLock()

    def _assert_role_state(self, host_id, rolename, state):
        role_assoc = self._db.get_current_role_association(host_id,
                                                           rolename)
        self.assertEqual(state, role_assoc.current_state)

    def _lookup_rabbit_creds(self,
                          host_id=TEST_HOST['id'],
                          rolename='test-role'):
        creds = self._db.query_rabbit_credentials(host_id=host_id,
                                                  rolename=rolename)[0]
        transport_url = 'rabbit://%s:%s@localhost:5673/' % \
                            (creds.userid, creds.password)
        return (creds.userid, creds.password, transport_url)

    def _assert_event_handler_called(self, event_name, rolename='test-role',
                custom_value='default value for customizable_key'):
        """
        This may be called post-deauth, in which case the rabbit creds
        are gone from the DB. Use the mocked, hardcode RABBIT_USER,
        RABBIT_PASS and RABBIT_URL instead of querying for them.
        """
        events = sys.modules['test_auth_events']
        method = getattr(events, event_name)
        host_config = {
            'test_conf': {
                'DEFAULT': {
                    'conf1': 'conf1_value',
                    'rabbit_user': RABBIT_USER,
                    'rabbit_password': RABBIT_PASS,
                    'rabbit_transport_url': RABBIT_URL,
                    'legacy_rabbit_transport_url': RABBIT_URL,
                    'endpoint_spec': 'http://something/%(project_id)s'
                },
                'customizable_section': {
                    'customizable_key': custom_value
                }
            }
        }
        method.assert_called_once_with(logger=provider_logger,
                                       param1='param1_value',
                                       param2='param2_value',
                                       host_id = TEST_HOST['id'],
                                       host_config=host_config)

    def _assert_event_handler_not_called(self, event_name):
        events = sys.modules['test_auth_events']
        method = getattr(events, event_name)
        self.assertFalse(method.called)

    def _assert_same_rabbit_creds(self, host_id, expected):
        def _to_dict(cred):
            return {k: getattr(cred, k)
                    for k in ['rolename', 'host_id', 'password', 'userid']}
        actual = self._db.query_rabbit_credentials(host_id=host_id)
        expected_dicts = [_to_dict(cred) for cred in expected]
        actual_dicts = [_to_dict(cred) for cred in actual]
        self.assertEqual(len(expected), len(actual))
        for e in expected_dicts:
            self.assertIn(e, actual_dicts)

    def _assert_fails_puts_deletes(self, host_id, rolename):
        init = self._db.get_current_role_association(host_id,
                                                     rolename)
        init_state = role_states.from_name(init.current_state)
        init_rabbit_creds = self._db.query_rabbit_credentials(host_id=host_id)
        init_delete_calls = self._delete_rabbit_user.call_count
        with self.assertRaises(RoleUpdateConflict):
            self._provider.add_role(host_id, rolename, None, {})
        with self.assertRaises(RoleUpdateConflict):
            self._provider.delete_role(host_id, rolename)

        # make sure the state didn't change
        self._assert_role_state(host_id, rolename, init_state)

        # make sure the rabbit creds on the host didn't change
        self._assert_same_rabbit_creds(host_id, init_rabbit_creds)
        self.assertEqual(init_delete_calls, self._delete_rabbit_user.call_count)

    def _add_and_converge_role(self, rolename):
        host_id = TEST_HOST['id']
        self._provider.add_role(host_id, rolename, None, {})
        self._bbone.process_hosts()
        self._assert_event_handler_called('on_auth')
        self._assert_role_state(host_id, rolename,
                                role_states.AUTH_CONVERGING)
        self._get_backbone_host.return_value = self._converged_host()
        self._bbone.process_hosts()
        self._assert_event_handler_called('on_auth_converged')
        self._requests_put.assert_called_with(
                'http://fake/v1/hosts/1234/apps',
                match_dict_to_jsonified(BBONE_PUSH))
        authed_host = self._inventory.get_authorized_host(host_id)
        self.assertEqual('ok', authed_host.get('role_status'))
        self._assert_role_state(host_id, rolename, role_states.APPLIED)

    @staticmethod
    def _fail_auth_event(event_name):
        """
        Auth events are loaded later. This tells the test_auth_events
        module to raise an exception on the named event.
        """
        os.environ['PF9_RESMGR_FAIL_EVENT'] = event_name

    def _unfail_auth_event(self, event_name):
        """
        Remove the environment variable so all events succeed
        """
        popped = os.environ.pop('PF9_RESMGR_FAIL_EVENT', None)
        self.assertEqual(event_name, popped)

    def test_valid_roles(self):
        good_role = self._provider.get_role('test-role')
        self.assertEqual(good_role['test-role']['name'], 'test-role')
        bad_role = self._provider.get_role('role-missing-config')
        self.assertEqual(bad_role, None)

    def test_core646(self):
        # Reproduces the race condition of CORE-646

        # Set to False before fix, and True after fix
        bug_fixed = True
        host_id = TEST_HOST['id']
        self._provider.add_role(host_id, 'test-role', None, {})

        def preemptive_func():
            self._provider.add_role(host_id, 'test-role-2', None, {})

        self._bbone.process_hosts(post_db_read_hook_func=preemptive_func)

        self._assert_role_state(host_id, 'test-role',
                                role_states.AUTH_CONVERGING)

        expected_role2_state = role_states.PRE_AUTH if bug_fixed else \
                               role_states.AUTH_CONVERGING
        self._assert_role_state(host_id, 'test-role-2', expected_role2_state)
        url = 'http://fake/v1/hosts/1234/apps'
        if not bug_fixed:
            # The following sequence occurs before the fix to CORE-646:
            # - 2 pushes of a config that contains both roles
            # - a push of a config that contains only test-role
            self._requests_put.assert_has_calls([
                ((url, match_dict_to_jsonified(BBONE_COMBINED_PUSH)),{}),
                ((url, match_dict_to_jsonified(BBONE_COMBINED_PUSH)),{}),
                ((url, match_dict_to_jsonified(BBONE_PUSH)),{}),
            ])
        else:
            # The following sequence occurs after CORE-646 is fixed:
            # 2 pushes containing only test-role
            self._requests_put.assert_has_calls([
                ((url, match_dict_to_jsonified(BBONE_PUSH)),{}),
                ((url, match_dict_to_jsonified(BBONE_PUSH)),{}),
            ])
            # It takes another process_hosts() for test-role-2 to be pushed
            self._bbone.process_hosts()
            self._requests_put.assert_has_calls([
                ((url, match_dict_to_jsonified(BBONE_PUSH)),{}),
                ((url, match_dict_to_jsonified(BBONE_PUSH)),{}),
                ((url, match_dict_to_jsonified(BBONE_COMBINED_PUSH)), {}),
                ((url, match_dict_to_jsonified(BBONE_COMBINED_PUSH)), {}),
            ])

    def test_add_role_default_config(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._add_role_default_config(host_id, rolename, None)

    def test_add_non_active_role_default_config(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        #self._add_role_default_config(host_id, rolename, "0.5")

    def _add_role_default_config(self, host_id, rolename, roleversion):
        self._provider.add_role(host_id, rolename, roleversion, {})
        self._bbone.process_hosts()

        self._assert_role_state(host_id, 'test-role',
                                role_states.AUTH_CONVERGING)
        self._assert_event_handler_called('on_auth')
        self._assert_fails_puts_deletes(host_id, 'test-role')

        # check the config that got pushed to bbmaster
        self._requests_put.assert_called_with(
            'http://fake/v1/hosts/1234/apps',
            match_dict_to_jsonified(BBONE_PUSH))

        hosts = self._provider.get_all_hosts()
        self.assertEqual(1, len(hosts))
        host = hosts.get(host_id)
        self.assertTrue(host)
        self.assertTrue('test-role' in host['roles'])

        authed_host = self._inventory.get_authorized_host(host_id)
        self.assertFalse(authed_host.get('role_status'))

        # send a converging event from bbone poller
        self._get_backbone_host.return_value = self._converging_host()
        self._bbone.process_hosts()
        authed_host = self._inventory.get_authorized_host(host_id)
        self.assertEqual('converging', authed_host.get('role_status'))
        self._assert_role_state(host_id, 'test-role',
                                role_states.AUTH_CONVERGING)
        self._assert_event_handler_not_called('on_auth_converged')
        self._assert_fails_puts_deletes(host_id, 'test-role')

        # update with an old timestamp, should ignore
        self._get_backbone_host.return_value = \
            self._converged_host(old_timestamp=True)
        self._bbone.process_hosts()
        authed_host = self._inventory.get_authorized_host(host_id)
        self.assertEqual('converging', authed_host.get('role_status'))
        self._assert_role_state(host_id, 'test-role',
                                role_states.AUTH_CONVERGING)
        self._assert_event_handler_not_called('on_auth_converged')
        self._assert_fails_puts_deletes(host_id, 'test-role')

        # our pretend host has converged (fresh bbone update)
        self._get_backbone_host.return_value = self._converged_host()
        self._bbone.process_hosts()
        authed_host = self._inventory.get_authorized_host(host_id)
        self.assertEqual('ok', authed_host.get('role_status'))
        self._assert_role_state(host_id, 'test-role',
                                role_states.APPLIED)
        self._assert_event_handler_called('on_auth_converged')

    def test_delete_role(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._add_and_converge_role(rolename)

        # delete it
        self._provider.delete_role(host_id, rolename)
        self._bbone.process_hosts()

        # check that empty config was pushed to bbmaster.
        self._requests_put.assert_called_with(
            'http://fake/v1/hosts/1234/apps', '{}')

        self._assert_role_state(host_id, 'test-role',
                                role_states.DEAUTH_CONVERGING)
        self._assert_event_handler_called('on_deauth')
        self._assert_fails_puts_deletes(host_id, 'test-role')

        # still converging
        self._get_backbone_host.return_value = self._converging_host()
        self._bbone.process_hosts()
        self._assert_role_state(host_id, 'test-role',
                                role_states.DEAUTH_CONVERGING)
        self._assert_event_handler_not_called('on_deauth_converged')
        self._assert_fails_puts_deletes(host_id, 'test-role')

        # converged
        self._get_backbone_host.return_value = self._empty_host()
        self._bbone.process_hosts()

        # verify that the deauth post-converge event ran.
        self._assert_event_handler_called('on_deauth_converged')

        # host is gone
        hosts = self._inventory.get_all_hosts()
        self.assertFalse(hosts)

    def test_delete_one_role_keep_another(self):
        # add and converge both roles
        host_id = TEST_HOST['id']
        self._provider.add_role(host_id, 'test-role', None, {})
        self._provider.add_role(host_id, 'test-role-2', None, {})
        self._bbone.process_hosts()
        self._assert_fails_puts_deletes(host_id, 'test-role')

        # augment our canned host response to include both roles
        converged = self._converged_host()
        converged['apps']['test-role-2'] = converged['apps']['test-role']
        self._get_backbone_host.return_value = converged
        self._bbone.process_hosts()
        authed_host = self._inventory.get_authorized_host(host_id)
        self.assertEqual('ok', authed_host.get('role_status'))
        self.assertEqual(['test-role', 'test-role-2'],
                         sorted(authed_host['roles']))
        self._assert_role_state(host_id, 'test-role',
                                role_states.APPLIED)
        self._assert_role_state(host_id, 'test-role-2',
                                role_states.APPLIED)

        # delete the first one
        self._provider.delete_role(host_id, 'test-role')
        self._bbone.process_hosts()
        self._assert_role_state(host_id, 'test-role',
                                role_states.DEAUTH_CONVERGING)
        self._assert_fails_puts_deletes(host_id, 'test-role')

        # verify that the deauth events ran.
        self._assert_event_handler_called('on_deauth')

        # The host is still authorized, and the role's still there
        host = self._inventory.get_authorized_host(host_id)
        self.assertTrue(host)
        self.assertCountEqual(['test-role', 'test-role-2'], host['roles'])

        # still in the database with test-role-2 still bound
        hosts_in_db = self._db.query_hosts()
        self.assertTrue(hosts_in_db)
        self.assertCountEqual(['test-role', 'test-role-2'],
                          hosts_in_db[0]['roles'])

        # cleanup's still in process on the host.
        converging = copy.deepcopy(converged)
        del converging['apps']['test-role']
        converging['desired_apps'] = converging.pop('apps')
        converging['status'] = 'converging'
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')
        converging['timestamp'] = converging['timestamp_on_du'] = timestamp
        self._get_backbone_host.return_value = converging
        self._bbone.process_hosts()
        hosts = self._inventory.get_all_hosts()
        self.assertEqual(1, len(hosts))
        host = hosts.get(host_id)
        self.assertTrue(host)
        self.assertEqual('converging', host['role_status'])
        self.assertCountEqual(['test-role', 'test-role-2'],
                          host.get('roles'))
        self._assert_event_handler_not_called('on_deauth_converged')
        self._assert_role_state(host_id, 'test-role',
                                role_states.DEAUTH_CONVERGING)
        self._assert_fails_puts_deletes(host_id, 'test-role')

        # our pretend host has converged
        del converged['apps']['test-role']
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')
        converged['timestamp'] = converged['timestamp_on_du'] = timestamp
        self._get_backbone_host.return_value = converged
        self._bbone.process_hosts()
        authed_host = self._inventory.get_authorized_host(host_id)
        self.assertEqual('ok', authed_host.get('role_status'))
        self.assertEqual(['test-role-2'], authed_host.get('roles'))
        self._assert_event_handler_called('on_deauth_converged')

    def test_upgrade_role(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._add_and_converge_role(rolename)

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

        # re-PUT the role
        self._provider.add_role(host_id, rolename, None, {})
        self._bbone.process_hosts()
        self._assert_role_state(host_id, 'test-role',
                                role_states.AUTH_CONVERGING)
        self._assert_fails_puts_deletes(host_id, 'test-role')

        # check the config that got pushed to bbmaster
        push_2_0 = copy.deepcopy(BBONE_PUSH)
        push_2_0['test-role']['version'] = '2.0'
        self._requests_put.assert_called_with(
                'http://fake/v1/hosts/1234/apps',
                match_dict_to_jsonified(push_2_0))

        # converging new role
        converging_2_0 = self._converging_host()
        converging_2_0['desired_apps']['test-role']['version'] = '2.0'
        self._get_backbone_host.return_value = converging_2_0
        self._bbone.process_hosts()
        host = self._inventory.get_authorized_host(host_id)
        self.assertTrue(host)
        self.assertEqual('converging', host['role_status'])
        self.assertEqual(['test-role'], host.get('roles'))
        self._assert_role_state(host_id, 'test-role',
                                role_states.AUTH_CONVERGING)
        self._assert_fails_puts_deletes(host_id, 'test-role')

        # successfully converged new role
        converged_2_0 = self._converged_host()
        converged_2_0['apps']['test-role']['version'] = '2.0'
        self._get_backbone_host.return_value = converged_2_0
        self._bbone.process_hosts()

        authed_host = self._inventory.get_authorized_host(host_id)
        self.assertEqual('ok', authed_host.get('role_status'))
        self.assertEqual(['test-role'], authed_host.get('roles'))

        roles = self._db.query_roles_for_host(host_id)
        self.assertEqual(1, len(roles))
        self.assertEqual('test-role_2.0', roles[0].id)
        self.assertEqual('2.0', roles[0].version)
        self._assert_role_state(host_id, 'test-role', role_states.APPLIED)

    def test_edit_role(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._add_and_converge_role(rolename)

        # re-PUT the role with new configurable param
        custom_value = 'new value for customizable_key'
        new_role_params ={'customizable_key': custom_value}
        self._provider.add_role(host_id, rolename, None, new_role_params)
        self._bbone.process_hosts()
        self._assert_role_state(host_id, 'test-role',
                                role_states.AUTH_CONVERGING)
        self._assert_fails_puts_deletes(host_id, 'test-role')
        self._assert_event_handler_called('on_auth', custom_value=custom_value)

        # check the config that got pushed to bbmaster
        push = copy.deepcopy(BBONE_PUSH)
        push['test-role']['config']['test_conf']['customizable_section'
            ].update(new_role_params)
        self._requests_put.assert_called_with(
                'http://fake/v1/hosts/1234/apps',
                match_dict_to_jsonified(push))

        # converging new role
        converging = self._converging_host()
        converging['desired_apps']['test-role']['config']['test_conf'
            ]['customizable_section'].update(new_role_params)
        self._get_backbone_host.return_value = converging
        self._bbone.process_hosts()
        host = self._inventory.get_authorized_host(host_id)
        self.assertTrue(host)
        self.assertEqual('converging', host['role_status'])
        self.assertEqual(['test-role'], host.get('roles'))
        self._assert_role_state(host_id, 'test-role',
                                role_states.AUTH_CONVERGING)
        self._assert_fails_puts_deletes(host_id, 'test-role')

        # successfully converged new role
        converged = self._converged_host()
        converged['apps']['test-role']['config']['test_conf'
            ]['customizable_section'].update(new_role_params)
        self._get_backbone_host.return_value = converged
        self._bbone.process_hosts()

        authed_host = self._inventory.get_authorized_host(host_id)
        self.assertEqual('ok', authed_host.get('role_status'))
        self.assertEqual(['test-role'], authed_host.get('roles'))
        self._assert_role_state(host_id, 'test-role',
                                role_states.APPLIED)

    def test_failed_on_auth_event(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._fail_auth_event('on_auth')
        with self.assertRaises(DuConfigError):
            self._provider.add_role(host_id, rolename, None, {})
        self._assert_role_state(host_id, 'test-role',
                                role_states.NOT_APPLIED)

    def test_failed_on_auth_event_edit(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._add_and_converge_role(rolename)

        self._fail_auth_event('on_auth')
        with self.assertRaises(DuConfigError):
            self._provider.add_role(host_id, rolename, None, {})

        # should still be applied
        self._assert_role_state(host_id, 'test-role',
                                role_states.APPLIED)

    def test_failed_on_deauth_event(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._add_and_converge_role(rolename)
        init_rabbit_creds = self._db.query_rabbit_credentials(host_id=host_id)
        init_delete_calls = self._delete_rabbit_user.call_count
        self.assertTrue(init_rabbit_creds)

        # try to deauth, but the event fails
        self._fail_auth_event('on_deauth')
        with self.assertRaises(DuConfigError):
            self._provider.delete_role(host_id, rolename)

        # make sure the rabbit creds didn't change
        self._assert_same_rabbit_creds(host_id, init_rabbit_creds)
        self.assertEqual(init_delete_calls, self._delete_rabbit_user.call_count)

    def test_failed_on_auth_converged_event(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._fail_auth_event('on_auth_converged')

        # add and converge the role. The end state should be AUTH_EROR
        self._provider.add_role(host_id, rolename, None, {})
        self._bbone.process_hosts()
        self._get_backbone_host.return_value = self._converged_host()
        self._bbone.process_hosts()
        self._assert_role_state(host_id, rolename, role_states.AUTH_ERROR)

        # now try to recover
        self._unfail_auth_event('on_auth_converged')
        self._provider.add_role(host_id, rolename, None, {})
        self._bbone.process_hosts()
        self._assert_role_state(host_id, rolename, role_states.AUTH_CONVERGING)
        self._get_backbone_host.return_value = self._converged_host()
        self._bbone.process_hosts()
        self._assert_role_state(host_id, rolename, role_states.APPLIED)

    def test_failed_on_deauth_converged_event(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._add_and_converge_role(rolename)

        # start deauth, on_deauth_converged event will put us in DEAUTH_ERROR
        self._fail_auth_event('on_deauth_converged')
        self._provider.delete_role(host_id, rolename)
        self._bbone.process_hosts()
        self._get_backbone_host.return_value = self._empty_host()
        self._bbone.process_hosts()
        self._assert_role_state(host_id, rolename, role_states.DEAUTH_ERROR)

        # add should fail:
        with self.assertRaises(RoleUpdateConflict):
            self._provider.add_role(host_id, rolename, None, {})

        # now try to recover with a delete
        self._unfail_auth_event('on_deauth_converged')
        self._provider.delete_role(host_id, rolename)
        self._bbone.process_hosts()
        self._assert_role_state(host_id, rolename,
                                role_states.DEAUTH_CONVERGING)
        self._get_backbone_host.return_value = self._empty_host()
        self._bbone.process_hosts()

        # verify that the deauth post-converge event ran.
        self._assert_event_handler_called('on_deauth_converged')

        # host is gone
        hosts = self._inventory.get_all_hosts()
        self.assertFalse(hosts)

    def test_delete_host(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._add_and_converge_role(rolename)

        # delete the host and converge it
        self._provider.delete_host(host_id)
        self._bbone.process_hosts()

        # host should be there until converged
        self.assertTrue(self._inventory.get_all_hosts(),
                        'deleted host should exist until converge')
        self._assert_role_state(host_id, 'test-role',
                                role_states.DEAUTH_CONVERGING)
        self._assert_event_handler_called('on_deauth')
        self._get_backbone_host.return_value = self._empty_host()
        self._bbone.process_hosts()
        self._assert_event_handler_called('on_deauth_converged')

        # host is gone
        hosts = self._inventory.get_all_hosts()
        self.assertFalse(hosts)

    def test_crash_from_start_apply(self):
        host_id = TEST_HOST['id']

        # induce a failure in the state transition:
        with mock.patch.object(self._provider.roles_mgr,
                'move_to_preauth_state') as move_to_preauth_state:
            move_to_preauth_state.side_effect = RuntimeError()
            with self.assertRaises(RuntimeError):
                self._provider.add_role(host_id, 'test-role', None, {})

        # we should be in START_APPLY now
        self._assert_role_state(host_id, 'test-role',
                                role_states.START_APPLY)
        # 'restart' resmgr: fire the bb poller
        self._get_backbone_host.return_value = self._empty_host()
        self._bbone.process_hosts()

        # it should run on_auth, and push the new app
        self._assert_event_handler_called('on_auth')
        self._requests_put.assert_called_with(
                'http://fake/v1/hosts/1234/apps',
                match_dict_to_jsonified(BBONE_PUSH))
        self._assert_role_state(host_id, 'test-role',
                                role_states.AUTH_CONVERGING)

        # later the host reports it converged
        self._get_backbone_host.return_value = self._converged_host()
        self._bbone.process_hosts()
        self._assert_event_handler_called('on_auth_converged')
        self._assert_role_state(host_id, 'test-role',
                                role_states.APPLIED)

    def test_crash_from_start_edit(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._add_and_converge_role(rolename)

        # induce a failure in the state transition:
        with mock.patch.object(self._provider.roles_mgr,
                'move_to_preauth_state') as move_to_preauth_state:
            move_to_preauth_state.side_effect = RuntimeError()
            custom_value = 'new value for customizable_key'
            with self.assertRaises(RuntimeError):
                new_role_params ={'customizable_key': custom_value}
                self._provider.add_role(host_id, rolename, None, new_role_params)

        # we should be in START_EDIT now
        self._assert_role_state(host_id, 'test-role',
                                role_states.START_EDIT)
        # 'restart' resmgr: fire the bb poller
        self._get_backbone_host.return_value = self._converged_host()
        self._bbone.process_hosts()

        # it should run on_auth, and push the new app
        self._assert_event_handler_called('on_auth', custom_value=custom_value)
        push = copy.deepcopy(BBONE_PUSH)
        push['test-role']['config']['test_conf']['customizable_section'
            ].update(new_role_params)
        self._requests_put.assert_called_with(
                'http://fake/v1/hosts/1234/apps',
                match_dict_to_jsonified(push))

        # converging new role
        converging = self._converging_host()
        converging['desired_apps']['test-role']['config']['test_conf'
            ]['customizable_section'].update(new_role_params)
        self._get_backbone_host.return_value = converging
        self._bbone.process_hosts()
        self._assert_role_state(host_id, 'test-role',
                                role_states.AUTH_CONVERGING)

        # successfully converged new role
        converged = self._converged_host()
        converged['apps']['test-role']['config']['test_conf'
            ]['customizable_section'].update(new_role_params)
        self._get_backbone_host.return_value = converged
        self._bbone.process_hosts()

        authed_host = self._inventory.get_authorized_host(host_id)
        self.assertEqual('ok', authed_host.get('role_status'))
        self.assertEqual(['test-role'], authed_host.get('roles'))
        self._assert_role_state(host_id, 'test-role',
                                role_states.APPLIED)

    def test_crash_from_start_deauth(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._add_and_converge_role(rolename)

        # induce a failure in the state transition:
        with mock.patch.object(self._provider.roles_mgr,
                'move_to_pre_deauth_state') as move_to_pre_deauth_state:
            move_to_pre_deauth_state.side_effect = RuntimeError()
            with self.assertRaises(RuntimeError):
                self._provider.delete_role(host_id, 'test-role')

        # we should be in START_DEAUTH now
        self._assert_role_state(host_id, 'test-role',
                                role_states.START_DEAUTH)
        # 'restart' resmgr: fire the bb poller
        self._get_backbone_host.return_value = self._converged_host()
        self._bbone.process_hosts()

        # it should run on_deauth, and push the empty apps config
        self._assert_event_handler_called('on_deauth')
        self._requests_put.assert_called_with(
                'http://fake/v1/hosts/1234/apps',
                match_dict_to_jsonified({}))
        self._assert_role_state(host_id, 'test-role',
                                role_states.DEAUTH_CONVERGING)

        # later the host reports it converged
        self._get_backbone_host.return_value = self._empty_host()
        self._bbone.process_hosts()
        self._assert_event_handler_called('on_deauth_converged')

        # host is gone
        hosts = self._inventory.get_all_hosts()
        self.assertFalse(hosts)

    def test_crash_from_pre_auth(self):
        host_id = TEST_HOST['id']

        # induce a failure in the push to bbmaster:
        with mock.patch.object(self._provider.roles_mgr,
                'push_configuration') as push_configuration:
            push_configuration.side_effect = RuntimeError()
            with self.assertRaises(RuntimeError):
                self._provider.add_role(host_id, 'test-role', None, {})
                self._bbone.process_hosts()


        # on_auth should have run, and we should be in PRE_AUTH
        self._assert_event_handler_called('on_auth')
        self._assert_role_state(host_id, 'test-role',
                                role_states.PRE_AUTH)

        # 'restart' resmgr: fire the bb poller
        self._get_backbone_host.return_value = self._empty_host()
        self._bbone.process_hosts()

        # it should run on_auth, and push the new app
        self._requests_put.assert_called_with(
                'http://fake/v1/hosts/1234/apps',
                match_dict_to_jsonified(BBONE_PUSH))
        self._assert_role_state(host_id, 'test-role',
                                role_states.AUTH_CONVERGING)

        # later the host reports it converged
        self._get_backbone_host.return_value = self._converged_host()
        self._bbone.process_hosts()
        self._assert_event_handler_called('on_auth_converged')
        self._assert_role_state(host_id, 'test-role',
                                role_states.APPLIED)

    def test_crash_from_pre_deauth(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._add_and_converge_role(rolename)

        # induce a failure in the push to bbmaster:
        with mock.patch.object(self._provider.roles_mgr,
                'push_configuration') as push_configuration:
            push_configuration.side_effect = RuntimeError()
            with self.assertRaises(RuntimeError):
                self._provider.delete_role(host_id, 'test-role')
                self._bbone.process_hosts()

        # on_deauth should have run, and we should be in PRE_DEAUTH
        self._assert_event_handler_called('on_deauth')
        self._assert_role_state(host_id, 'test-role',
                                role_states.PRE_DEAUTH)

        # 'restart' resmgr: fire the bb poller
        self._get_backbone_host.return_value = self._converged_host()
        self._bbone.process_hosts()

        # it should run on_auth, and push the new app
        self._requests_put.assert_called_with(
                'http://fake/v1/hosts/1234/apps',
                match_dict_to_jsonified({}))
        self._assert_role_state(host_id, 'test-role',
                                role_states.DEAUTH_CONVERGING)

        # later the host reports it converged
        self._get_backbone_host.return_value = self._empty_host()
        self._bbone.process_hosts()
        self._assert_event_handler_called('on_deauth_converged')

        # host is gone
        hosts = self._inventory.get_all_hosts()
        self.assertFalse(hosts)

    def test_crash_from_auth_converging(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._provider.add_role(host_id, rolename, None, {})
        self._bbone.process_hosts()
        self._assert_event_handler_called('on_auth')
        self._assert_role_state(host_id, rolename,
                                role_states.AUTH_CONVERGING)

        # induce a failure in the final state update to 'applied':
        with mock.patch.object(self._provider.roles_mgr,
                'move_to_applied_state') as move_to_applied_state:
            move_to_applied_state.side_effect = RuntimeError()
            with self.assertRaises(RuntimeError):
                self._get_backbone_host.return_value = self._converged_host()
                self._bbone.process_hosts()
        # should leave us in CONVERGED
        self._assert_role_state(host_id, rolename,
                                role_states.AUTH_CONVERGED)

        # make sure we're locked out
        custom_value = 'new value for customizable_key'
        new_role_params = {'customizable_key': custom_value}
        with self.assertRaises(RoleUpdateConflict):
            self._provider.add_role(host_id, rolename, None,
                                    new_role_params)

        # 'restart' resmgr: fire the bb poller
        self._get_backbone_host.return_value = self._converged_host()
        self._bbone.process_hosts()

        # runs on_auth_converged and finishes up.
        self._assert_event_handler_called('on_auth_converged',
                                          custom_value=custom_value)
        self._assert_role_state(host_id, 'test-role',
                                role_states.APPLIED)

    def test_crash_from_deauth_converging(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._add_and_converge_role(rolename)

        # delete the host and converge it
        self._provider.delete_role(host_id, rolename)
        self._bbone.process_hosts()
        self._assert_event_handler_called('on_deauth')
        self._assert_role_state(host_id, rolename,
                                role_states.DEAUTH_CONVERGING)

        # induce a failure in the final state update to 'not-applied':
        with mock.patch.object(self._provider.roles_mgr,
                'move_to_not_applied_state') as move_to_not_applied_state:
            move_to_not_applied_state.side_effect = RuntimeError()
            with self.assertRaises(RuntimeError):
                self._get_backbone_host.return_value = self._empty_host()
                self._bbone.process_hosts()
        # should leave us in CONVERGED
        self._assert_role_state(host_id, rolename,
                                role_states.DEAUTH_CONVERGED)

        # make sure we're locked out
        custom_value = 'new value for customizable_key'
        new_role_params ={'customizable_key': custom_value}
        with self.assertRaises(RoleUpdateConflict):
            self._provider.add_role(host_id, rolename, None,
                                    new_role_params)

        # 'restart' resmgr: fire the bb poller
        self._get_backbone_host.return_value = self._empty_host()
        self._bbone.process_hosts()

        # runs on_deauth_converged, removes the role and host
        self._assert_event_handler_called('on_deauth_converged',
                                          custom_value=custom_value)
        hosts = self._inventory.get_all_hosts()
        self.assertFalse(hosts)

    def test_deauth_unresponsive_host(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._add_and_converge_role(rolename)

        # host is not responsive
        self._responding_within_threshold.return_value = False

        # delete it
        self._provider.delete_role(host_id, rolename)
        self._assert_event_handler_called('on_deauth')
        self._assert_fails_puts_deletes(host_id, 'test-role')
        self._bbone.process_hosts()

        # check that empty config was pushed to bbmaster.
        self._requests_put.assert_called_with(
            'http://fake/v1/hosts/1234/apps', '{}')

        # bbmaster still thinks the host is empty
        self._get_backbone_host.return_value = self._empty_host()

        # the host isn't responding, so it should converge, call the
        # post-deauth-converge hook and finish up.
        self._bbone.process_hosts()
        self._assert_event_handler_called('on_deauth_converged')

        # host is gone
        hosts = self._inventory.get_all_hosts()
        self.assertFalse(hosts)

    def test_deauth_missing_host(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._add_and_converge_role(rolename)

        # host is not responsive
        self._responding_within_threshold.return_value = False

        # delete it
        self._provider.delete_role(host_id, rolename)
        self._assert_event_handler_called('on_deauth')
        self._assert_fails_puts_deletes(host_id, 'test-role')

        # the host isn't responding, so it should converge, call the
        # post-deauth-converge hook and finish up.
        self._get_backbone_host.return_value = MISSING_BBONE_HOST
        self._bbone.process_hosts()

        # check that empty config was pushed to bbmaster.
        self._requests_put.assert_called_with(
            'http://fake/v1/hosts/1234/apps', '{}')

        # the host isn't responding, so it should converge, call the
        # post-deauth-converge hook and finish up.
        self._bbone.process_hosts()
        self._assert_event_handler_called('on_deauth_converged')

        # host is gone
        hosts = self._inventory.get_all_hosts()
        self.assertFalse(hosts)

    def test_add_role_unresponsive_host(self):
        # add a role so the host isn't deleted
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._add_and_converge_role(rolename)

        # host is not responsive - let the bbone poller notice it
        self._responding_within_threshold.return_value = False
        self._get_backbone_host.return_value = self._converged_host()
        self._bbone.process_hosts()

        with self.assertRaises(HostDown):
            self._provider.add_role(host_id, 'test-role-2', None, {})

        with self.assertRaises(HostDown):
            self._provider.add_role(host_id, 'test-role', '0.5', {})


    def test_delete_role_from_auth_error(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._provider.add_role(host_id, rolename, None, {})
        self._bbone.process_hosts()
        self._assert_event_handler_called('on_auth')
        self._assert_role_state(host_id, rolename,
                                role_states.AUTH_CONVERGING)
        self._get_backbone_host.return_value = self._failed_host()
        self._bbone.process_hosts()
        self._assert_role_state(host_id, rolename,
                                role_states.AUTH_ERROR)

        # delete it
        self._provider.delete_role(host_id, rolename)
        self._bbone.process_hosts()

        # check that empty config was pushed to bbmaster.
        self._requests_put.assert_called_with(
            'http://fake/v1/hosts/1234/apps', '{}')

        self._assert_role_state(host_id, 'test-role',
                                role_states.DEAUTH_CONVERGING)
        self._assert_event_handler_called('on_deauth')
        self._assert_fails_puts_deletes(host_id, 'test-role')

        # bbone hasn't got new update from hostagent since the delete call.
        # _process_existing_hosts should ignore it, even though it reports
        # 'failed'.
        self._bbone.process_hosts()
        self._assert_role_state(host_id, rolename,
                                role_states.DEAUTH_CONVERGING)

        # now it's converging
        self._get_backbone_host.return_value = self._converging_host()
        self._bbone.process_hosts()
        self._assert_role_state(host_id, 'test-role',
                                role_states.DEAUTH_CONVERGING)
        self._assert_event_handler_not_called('on_deauth_converged')
        self._assert_fails_puts_deletes(host_id, 'test-role')

        # converged
        self._get_backbone_host.return_value = self._empty_host()
        self._bbone.process_hosts()

        # verify that the deauth post-converge event ran.
        self._assert_event_handler_called('on_deauth_converged')

        # host is gone
        hosts = self._inventory.get_all_hosts()
        self.assertFalse(hosts)

    def test_missing_auth_events_file(self):
        # add a role so the host isn't deleted
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._add_and_converge_role(rolename)

        module_path = TEST_ROLE['test-role']['1.0']['config']['test-role'
                              ]['du_config']['auth_events']['module_path']
        real_isfile = os.path.isfile
        isfile = self._patchfun('os.path.isfile')
        isfile.side_effect = \
            lambda f: False if f == module_path else real_isfile(f)

        # delete it
        self._provider.delete_role(host_id, rolename)
        self._bbone.process_hosts()

        # check that empty config was pushed to bbmaster.
        self._requests_put.assert_called_with(
            'http://fake/v1/hosts/1234/apps', '{}')

        self._assert_role_state(host_id, 'test-role',
                                role_states.DEAUTH_CONVERGING)
        self._assert_fails_puts_deletes(host_id, 'test-role')

        # converged
        self._get_backbone_host.return_value = self._empty_host()
        self._bbone.process_hosts()

        # host is gone
        hosts = self._inventory.get_all_hosts()
        self.assertFalse(hosts)

    def test_iaas_8990(self):
        # start the poller with a short poll interval
        pollthread = threading.Thread(target=self._bbone.run)
        pollthread.daemon = True

        # this is backup of thread.start() that's mocked by setUp
        self._real_thread_start(pollthread)

        # add and converge the role at v1.0
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._provider.add_role(host_id, rolename, None, {})
        self._assert_event_handler_called('on_auth')
        time.sleep(2)
        self._assert_role_state(host_id, rolename,
                                role_states.AUTH_CONVERGING)

        # it should converge in one iteration of the poller
        self._get_backbone_host.return_value = self._converged_host()
        time.sleep(2)
        self._assert_role_state(host_id, rolename,
                                role_states.APPLIED)
        authed_host = self._inventory.get_authorized_host(host_id)
        self.assertEqual('ok', authed_host.get('role_status'))

        # upgrade from 1.0 to 1.50 by 0.01 at random intervals
        random.seed()
        for i in range(1, 50):
            new_version = '1.%0.2d' % i
            LOG.info('upgrading to %s', new_version)
            new_role = {
                'test-role': {
                    new_version: copy.deepcopy(TEST_ROLE['test-role']['1.0'])
                }
            }
            new_role['test-role'][new_version]['role_version'] = new_version
            new_role['test-role'][new_version][
                     'config']['test-role']['version'] = new_version
            self._load_roles_from_files.return_value = new_role
            self._db.setup_roles()

            # re-PUT the role
            self._provider.add_role(host_id, rolename, None, {})

            # add_role wakes up the poller and it starts converging
            time.sleep(1)
            self._assert_role_state(host_id, rolename,
                                    role_states.AUTH_CONVERGING)

            converged = self._converged_host()
            converged['apps']['test-role']['version'] = new_version
            self._get_backbone_host.return_value = converged

            # check the config that got pushed to bbmaster
            push = copy.deepcopy(BBONE_PUSH)
            push['test-role']['version'] = new_version
            self._requests_put.assert_called_with(
                    'http://fake/v1/hosts/1234/apps',
                    match_dict_to_jsonified(push))
            # one more iteration and it should complete
            time.sleep(2)
            authed_host = self._inventory.get_authorized_host(host_id)
            self.assertEqual('ok', authed_host.get('role_status'))
            self.assertEqual(['test-role'], authed_host.get('roles'))

            roles = self._db.query_roles_for_host(host_id)
            self.assertEqual(1, len(roles))
            self.assertEqual('test-role_%s' % new_version, roles[0].id)
            self.assertEqual(new_version, roles[0].version)
            self._assert_role_state(host_id, 'test-role', role_states.APPLIED)

            # random sleep between .25 and 2.25 seconds
            delay = 0.25 + 2 * random.random()
            time.sleep(delay)
        self._bbone.stop()
        pollthread.join()

    @staticmethod
    def _plain_http_response(code):
        resp = requests.Response()
        resp.status_code = code
        return resp

    @staticmethod
    def _unauthed_host():
        return copy.deepcopy(BBONE_HOST)

    def _converging_host(self, old_timestamp=False):
        return self._host_info('desired_apps', 'converging', old_timestamp)

    def _converged_host(self, old_timestamp=False):
        return self._host_info('apps', 'ok', old_timestamp)

    def _failed_host(self, old_timestamp=False):
        return self._host_info('desired_apps', 'failed', old_timestamp)

    @staticmethod
    def _empty_host(old_timestamp=False):
        host = copy.deepcopy(BBONE_HOST)
        host.update({'apps': {}})
        host['status'] = 'ok'
        if not old_timestamp:
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')
            host['timestamp'] = timestamp
            host['timestamp_on_du'] = timestamp
        return host

    def _host_info(self, apps_key, host_status, old_timestamp):
        host = copy.deepcopy(BBONE_HOST)
        apps = copy.deepcopy(BBONE_APPS)
        rabbit_creds = self._lookup_rabbit_creds(BBONE_HOST['host_id'],
                                                 'test-role')
        apps['test-role']['config']['test_conf']['DEFAULT'].update({
            'rabbit_user': rabbit_creds[0],
            'rabbit_password': rabbit_creds[1],
            'rabbit_transport_url': rabbit_creds[2]
        })
        host.update({apps_key: apps})
        host['status'] = host_status
        if not old_timestamp:
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')
            host['timestamp'] = timestamp
            host['timestamp_on_du'] = timestamp
        return host
