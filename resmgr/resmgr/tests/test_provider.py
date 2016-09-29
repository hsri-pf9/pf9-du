# Copyright (c) 2016 Platform9 Systems Inc. All Rights Reserved.

# pylint: disable=protected-access, too-many-instance-attributes
# pylint: disable=too-few-public-methods

import copy
import json
import logging
import mock
import os
import requests
import sys
import threading

from rabbit import RabbitMgmtClient
from resmgr import resmgr_provider_pf9
from resmgr import role_states
from resmgr.exceptions import DuConfigError, RoleUpdateConflict
from resmgr.resmgr_provider_pf9 import ResMgrPf9Provider, BbonePoller
from resmgr.resmgr_provider_pf9 import log as provider_logger
from resmgr.tests.dbtestcase import DbTestCase
from resmgr.tests.dbtestcase import TEST_HOST, TEST_ROLE

logging.basicConfig(level=logging.DEBUG)
LOG = logging.getLogger(__name__)

THISDIR = os.path.abspath(os.path.dirname(__file__))

BBONE_IDS = set([TEST_HOST['id']])
BBONE_HOST = {
    'extensions': {
        'interfaces': {
            'data': {
                'iface_ip': {u'eth0': '10.4.253.124'},
                'ovs_bridges': []
            },
            'status': u'ok'
        },
        'ip_address': {
            'data': [u'10.4.253.124'],
            'status': u'ok'
        },
        'volumes_present': {
            'data': [
                {'free': '0', 'name': 'ubuntu12-vg', 'size': '16.76g'}
            ],
            'status': u'ok'
        }
    },
    'host_agent': {'status': 'running', 'version': u'2.2.0-1463.5ae865b'},
    'host_id': '24bbbc8d-fe3c-4675-a5ab-6940af506cc7',
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

BBONE_APPS = {
    "test-role": {
        "version": "1.0",
        "service_states": {"test-service": "true"},
        "config": {
            "test_conf": {
                "DEFAULT": {
                    "conf1": "conf1_value"
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

        # FIXME: verify rabbit setup calls
        self._patchobj(RabbitMgmtClient, 'create_user')
        self._patchobj(RabbitMgmtClient, 'delete_user')
        self._patchobj(RabbitMgmtClient, 'set_permissions')

        # FIXME: check service config
        self._patchobj(ResMgrPf9Provider, 'run_service_config')

        # don't start the BbonePoller in a thread. The tests will call
        # process_hosts directly when appropriate.
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
        self.assertEquals(state, role_assoc.current_state)

    @staticmethod
    def _assert_event_handler_called(event_name):
        events = sys.modules['test_auth_events']
        method = getattr(events, event_name)
        method.assert_called_once_with(logger=provider_logger,
                                       param1='param1_value',
                                       param2='param2_value',
                                       host_id = TEST_HOST['id'])

    def _assert_event_handler_not_called(self, event_name):
        events = sys.modules['test_auth_events']
        method = getattr(events, event_name)
        self.assertFalse(method.called)

    def _assert_fails_puts_deletes(self, host_id, rolename):
        init = self._db.get_current_role_association(host_id,
                                                     rolename)
        init_state = role_states.from_name(init.current_state)
        with self.assertRaises(RoleUpdateConflict):
            self._provider.add_role(host_id, rolename, {})
        with self.assertRaises(RoleUpdateConflict):
            self._provider.delete_role(host_id, rolename)

        # make sure the state didn't change
        self._assert_role_state(host_id, rolename, init_state)

    def _add_and_converge_role(self, rolename):
        host_id = TEST_HOST['id']
        self._provider.add_role(host_id, rolename, {})
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
        self.assertEquals(event_name, popped)

    def test_add_role_default_config(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._provider.add_role(host_id, rolename, {})

        self._assert_role_state(host_id, 'test-role',
                                role_states.AUTH_CONVERGING)
        self._assert_event_handler_called('on_auth')
        self._assert_fails_puts_deletes(host_id, 'test-role')

        # check the config that got pushed to bbmaster
        self._requests_put.assert_called_once_with(
            'http://fake/v1/hosts/1234/apps',
            match_dict_to_jsonified(BBONE_PUSH))

        hosts = self._provider.get_all_hosts()
        self.assertEquals(1, len(hosts))
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

        # our pretend host has converged
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
        self._provider.add_role(host_id, 'test-role', {})
        self._provider.add_role(host_id, 'test-role-2', {})
        self._get_backbone_host.return_value = self._converged_host()
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
        self._assert_role_state(host_id, 'test-role',
                                role_states.DEAUTH_CONVERGING)
        self._assert_fails_puts_deletes(host_id, 'test-role')

        # verify that the deauth events ran.
        self._assert_event_handler_called('on_deauth')

        # The host is still authorized, and the role's still there
        host = self._inventory.get_authorized_host(host_id)
        self.assertTrue(host)
        self.assertEquals(['test-role', 'test-role-2'], host['roles'])

        # still in the database with test-role-2 still bound
        hosts_in_db = self._db.query_hosts()
        self.assertTrue(hosts_in_db)
        self.assertEquals(['test-role', 'test-role-2'],
                          hosts_in_db[0]['roles'])

        # cleanup's still in process on the host.
        self._get_backbone_host.return_value = self._converging_host()
        self._bbone.process_hosts()
        hosts = self._inventory.get_all_hosts()
        self.assertEquals(1, len(hosts))
        host = hosts.get(host_id)
        self.assertTrue(host)
        self.assertEquals('converging', host['role_status'])
        self.assertEquals(['test-role', 'test-role-2'],
                          host.get('roles'))
        self._assert_event_handler_not_called('on_deauth_converged')
        self._assert_role_state(host_id, 'test-role',
                                role_states.DEAUTH_CONVERGING)
        self._assert_fails_puts_deletes(host_id, 'test-role')

        # our pretend host has converged
        self._get_backbone_host.return_value = self._converged_host()
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
        self._provider.add_role(host_id, rolename, {})
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
        self.assertEquals('converging', host['role_status'])
        self.assertEquals(['test-role'], host.get('roles'))
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
        self.assertEquals(1, len(roles))
        self.assertEquals('test-role_2.0', roles[0].id)
        self.assertEquals('2.0', roles[0].version)
        self._assert_role_state(host_id, 'test-role', role_states.APPLIED)

    def test_edit_role(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._add_and_converge_role(rolename)

        # re-PUT the role with new configurable param
        new_role_params ={'customizable_key': 'new value for customizable_key'}
        self._provider.add_role(host_id, rolename, new_role_params)
        self._assert_role_state(host_id, 'test-role',
                                role_states.AUTH_CONVERGING)
        self._assert_fails_puts_deletes(host_id, 'test-role')

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
        self.assertEquals('converging', host['role_status'])
        self.assertEquals(['test-role'], host.get('roles'))
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
            self._provider.add_role(host_id, rolename, {})
        self._assert_role_state(host_id, 'test-role',
                                role_states.NOT_APPLIED)

    def test_failed_on_auth_event_edit(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._add_and_converge_role(rolename)

        self._fail_auth_event('on_auth')
        with self.assertRaises(DuConfigError):
            self._provider.add_role(host_id, rolename, {})

        # should still be applied
        self._assert_role_state(host_id, 'test-role',
                                role_states.APPLIED)

    def test_failed_on_deauth_event(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._add_and_converge_role(rolename)

        # try to deauth, but the event fails
        self._fail_auth_event('on_deauth')
        with self.assertRaises(DuConfigError):
            self._provider.delete_role(host_id, rolename)

    def test_failed_on_auth_converged_event(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._fail_auth_event('on_auth_converged')

        # add and converge the role. The end state should be AUTH_EROR
        self._provider.add_role(host_id, rolename, {})
        self._get_backbone_host.return_value = self._converged_host()
        self._bbone.process_hosts()
        self._assert_role_state(host_id, rolename, role_states.AUTH_ERROR)

        # now try to recover
        self._unfail_auth_event('on_auth_converged')
        self._provider.add_role(host_id, rolename, {})
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
        self._get_backbone_host.return_value = self._empty_host()
        self._bbone.process_hosts()
        self._assert_role_state(host_id, rolename, role_states.DEAUTH_ERROR)

        # add should fail:
        with self.assertRaises(RoleUpdateConflict):
            self._provider.add_role(host_id, rolename, {})

        # now try to recover with a delete
        self._unfail_auth_event('on_deauth_converged')
        self._provider.delete_role(host_id, rolename)
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
                self._provider.add_role(host_id, 'test-role', {})

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
            with self.assertRaises(RuntimeError):
                new_role_params ={'customizable_key':
                                  'new value for customizable_key'}
                self._provider.add_role(host_id, rolename, new_role_params)

        # we should be in START_EDIT now
        self._assert_role_state(host_id, 'test-role',
                                role_states.START_EDIT)
        # 'restart' resmgr: fire the bb poller
        self._get_backbone_host.return_value = self._converged_host()
        self._bbone.process_hosts()

        # it should run on_auth, and push the new app
        self._assert_event_handler_called('on_auth')
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
                self._provider.add_role(host_id, 'test-role', {})

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
        self._provider.add_role(host_id, rolename, {})
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
        new_role_params ={'customizable_key':
                          'new value for customizable_key'}
        with self.assertRaises(RoleUpdateConflict):
            self._provider.add_role(host_id, rolename,
                                    new_role_params)

        # 'restart' resmgr: fire the bb poller
        self._get_backbone_host.return_value = self._converged_host()
        self._bbone.process_hosts()

        # runs on_auth_converged and finishes up.
        self._assert_event_handler_called('on_auth_converged')
        self._assert_role_state(host_id, 'test-role',
                                role_states.APPLIED)

    def test_crash_from_deauth_converging(self):
        host_id = TEST_HOST['id']
        rolename = TEST_ROLE['test-role']['1.0']['role_name']
        self._add_and_converge_role(rolename)

        # delete the host and converge it
        self._provider.delete_role(host_id, rolename)
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
        new_role_params ={'customizable_key':
                          'new value for customizable_key'}
        with self.assertRaises(RoleUpdateConflict):
            self._provider.add_role(host_id, rolename,
                                    new_role_params)

        # 'restart' resmgr: fire the bb poller
        self._get_backbone_host.return_value = self._empty_host()
        self._bbone.process_hosts()

        # runs on_deauth_converged, removes the role and host
        self._assert_event_handler_called('on_deauth_converged')
        hosts = self._inventory.get_all_hosts()
        self.assertFalse(hosts)

    @staticmethod
    def _plain_http_response(code):
        resp = requests.Response()
        resp.status_code = code
        return resp

    @staticmethod
    def _unauthed_host():
        return copy.deepcopy(BBONE_HOST)

    @staticmethod
    def _converging_host():
        host = copy.deepcopy(BBONE_HOST)
        apps = copy.deepcopy(BBONE_APPS)
        host.update({'desired_apps': apps})
        host['status'] = 'converging'
        return host

    @staticmethod
    def _converged_host():
        host = copy.deepcopy(BBONE_HOST)
        apps = copy.deepcopy(BBONE_APPS)
        host.update({'apps': apps})
        host['status'] = 'ok'
        return host

    @staticmethod
    def _empty_host():
        host = copy.deepcopy(BBONE_HOST)
        host.update({'apps': {}})
        host['status'] = 'ok'
        return host
