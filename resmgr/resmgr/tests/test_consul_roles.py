# Copyright 2018 Platform9 Systems Inc. All Rights Reserved

import base64
import copy
import json
import logging
import os
import requests
import threading

from resmgr.consul_roles import ConsulRoles
from resmgr.dbutils import ResMgrDB
from resmgr.tests.dbtestcase import (
    DbTestCase,
    http_response,
    TEST_ROLE,
    TEST_HOST
)

CUSTOMER_ID = 'c1'
REGION_ID = 'r1'
ROLES_KEY = 'customers/%s/regions/%s/roles' % \
            (CUSTOMER_ID, REGION_ID)

LOG = logging.getLogger(__name__)

class TestConsulRoles(DbTestCase):

    def setUp(self):
        super(TestConsulRoles, self).setUp()

        # instantiate the db object, but don't start the consul watch thread
        self._patchobj(threading.Thread, 'start')

        # mock the request to consul
        self._requests_get = self._patchobj(requests.Session, 'get')
        self._requests_put = self._patchobj(requests.Session, 'put')
        self._index = 0
        self._requests_get.return_value = \
                http_response(200, self._index_header, [])
        self._requests_put.return_value = http_response(201, body='true')

        # environment settings for consul
        os.environ['CUSTOMER_ID'] = CUSTOMER_ID
        os.environ['REGION_ID'] = REGION_ID
        self._db = ResMgrDB(self._cfg)
        self._consul_roles = ConsulRoles(self._cfg, self._db)

    @property
    def _index_header(self):
        ret = {'X-Consul-Index': str(self._index)}
        self._index += 1
        return ret

    def test_new_role_from_consul(self):
        """
        add a brand new role from consul
        """
        roles = self._db.query_roles(active_only=False)
        rolename = 'role-from-consul'
        appname = 'app-from-consul'
        version = '1.0'
        new_role = copy.deepcopy(TEST_ROLE['test-role']['1.0'])
        new_role['role_version'] = version
        new_role['config'][appname] = new_role['config'].pop('test-role')
        new_role['config'][appname]['version'] = version

        consul_data = [{
            'Key': '%s/%s/%s/config' % (ROLES_KEY, rolename, version),
            'Value': base64.b64encode(json.dumps(new_role))
        }]
        self._requests_get.side_effect = [
            http_response(200, self._index_header, consul_data),
            KeyboardInterrupt()
        ]

        # check consul
        try:
            self._consul_roles._watch.run()
        except KeyboardInterrupt:
            pass
        roles = self._db.query_roles(active_only=False)
        new_role = None
        for role in roles:
            if role.rolename == rolename and role.version == version:
                new_role = role
                break
        self.assertTrue(new_role)
        self.assertEqual(True, new_role.active)
        self.assertEqual('%s_%s' % (rolename, version), new_role.id)

    def test_upgrade_role_from_consul(self):
        """
        upgrade the exising 'test-role', which is read in setUp using the
        normal (well, mocked) _load_roles_from_files in dbutils.
        """
        rolename = 'test-role'
        version = '1.2.1'
        LOG.info('upgrading to %s', version)
        new_role = copy.deepcopy(TEST_ROLE['test-role']['1.0'])
        new_role['role_version'] = version
        new_role['config']['test-role']['version'] = version
        consul_data = [{
            'Key': '%s/%s/%s/config' % (ROLES_KEY, rolename, version),
            'Value': base64.b64encode(json.dumps(new_role))
        }]
        self._requests_get.side_effect = [
            http_response(200, self._index_header, consul_data),
            KeyboardInterrupt()
        ]

        # check consul
        try:
            self._consul_roles._watch.run()
        except KeyboardInterrupt:
            pass
        roles = self._db.query_roles(active_only=False)
        new_role = None
        for role in roles:
            if role.rolename == rolename and role.version == version:
                new_role = role
                break
        self.assertTrue(new_role)
        self.assertEqual(True, new_role.active)
        self.assertEqual('%s_%s' % (rolename, version), new_role.id)

    def test_param_update(self):
        rolename = 'test-role'
        custom_params = {'customizable_key': 'customizable_value'}
        self._db.insert_update_host(TEST_HOST['id'],
                                    TEST_HOST['details'],
                                    rolename,
                                    custom_params)
        self._db.associate_role_to_host(TEST_HOST['id'], rolename)
        self._db.associate_rabbit_credentials_to_host(TEST_HOST['id'],
                                                      rolename,
                                                      'rabbituser',
                                                      'rabbitpass')

        # check current setting
        deets = self._db.query_host_and_app_details(
                    host_id=TEST_HOST['id'])
        self.assertEquals(1, len(deets))
        apps_cfg = deets[TEST_HOST['id']]['apps_config_including_deauthed_roles']
        self.assertEqual('conf1_value', apps_cfg[
            rolename]['config']['test_conf']['DEFAULT']['conf1'])
        self.assertEqual('param1_value', apps_cfg[
            rolename]['du_config']['auth_events']['params']['param1'])

        # update conf1 and param1
        consul_data = [{
            'Key': '%s/params/%s/conf1' % (ROLES_KEY, rolename),
            'Value': base64.b64encode('conf1_new_value')
        },{
            'Key': '%s/params/%s/param1' % (ROLES_KEY, rolename),
            'Value': base64.b64encode('param1_new_value')
        }]
        self._requests_get.side_effect = [
            http_response(200, self._index_header, consul_data),
            KeyboardInterrupt()
        ]
        try:
            self._consul_roles._watch.run()
        except KeyboardInterrupt:
            pass

        # check it
        deets = self._db.query_host_and_app_details(
                    host_id=TEST_HOST['id'])
        self.assertEquals(1, len(deets))
        self.assertEqual('conf1_new_value', deets[TEST_HOST['id']][
            'apps_config_including_deauthed_roles'][
            rolename]['config']['test_conf']['DEFAULT']['conf1'])
        self.assertEqual('param1_new_value', deets[TEST_HOST['id']][
            'apps_config_including_deauthed_roles'][
            rolename]['du_config']['auth_events']['params']['param1'])


