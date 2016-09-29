# Copyright 2016 Platform9 Systems Inc. All Rights Reserved

import logging
import mock

from resmgr.exceptions import RoleUpdateConflict, DuConfigError
from resmgr.tests import FunctionalTest
from resmgr.resmgr_provider_mem import ResMgrMemProvider

logging.basicConfig(level=logging.DEBUG)
LOG = logging.getLogger(__name__)

class TestResMgr(FunctionalTest):

    def _get_roles(self):
        response = self.app.get('/v1/roles')
        assert response is not None
        return response.json_body

    def _get_hosts(self):
        response = self.app.get('/v1/hosts')
        assert response is not None
        return response.json_body

    def _get_one_host(self, id):
        response = self.app.get(''.join(['/v1/hosts/',
                                         id]))
        assert response is not None
        return response.json_body

    def _get_single_role(self, id):
        response = self.app.get(''.join(['/v1/roles/',
                                         id]))
        assert response is not None
        return response.json_body

    def test_get_roles(self):
        roles = self._get_roles()
        assert type(roles) is list
        assert len(roles)

    def test_get_single_role(self):
        roles = self._get_roles()

        for item in roles:
            role = self._get_single_role(item['name'])
            assert role is not None

    def test_non_existing_data(self):
        fake_keys = ['dhfjshdkf', 'fhshfs']

        for fake in fake_keys:
            for path in ['/v1/hosts/', '/v1/roles/']:
                response = self.app.get(''.join([path,
                                                 fake]), expect_errors=True)
                assert response.status_int == 404

    def test_get_hosts(self):
        host = self._get_hosts()
        assert type(host) is list
        assert len(host)

    def test_associate(self):
        roles = [r['name'] for r in self._get_roles()]
        host = self._get_hosts()

        for (k1, k2) in zip(host, roles):
            k1_id = k1['id']
            self.app.put(''.join(['/v1/hosts/', k1_id, '/roles/', k2]))
            one_host = self._get_one_host(k1_id)

            assert one_host['roles']

            self.app.delete(''.join(['/v1/hosts/', k1_id, '/roles/', k2]))

            one_host = self._get_one_host(k1_id)

            assert not one_host['roles']

    def test_put_config(self):
        #TODO: Figure out how to test put operations
        pass

    def test_put_role_bad_state(self):
        with mock.patch.object(ResMgrMemProvider, 'add_role') as add_role:
            add_role.side_effect = RoleUpdateConflict('conflict!')
            resp = self.app.put('/v1/hosts/rsc_1/roles/test-role',
                                expect_errors=True)
            LOG.info('test_put_role_bad_state response body: %s', resp.text)
            self.assertTrue(resp.json.has_key('message'))
            self.assertEquals(409, resp.status_code)

    def test_put_role_on_auth_failure(self):
        with mock.patch.object(ResMgrMemProvider, 'add_role') as add_role:
            add_role.side_effect = DuConfigError('error!')
            resp = self.app.put('/v1/hosts/rsc_1/roles/test-role',
                                expect_errors=True)
            LOG.info('test_put_role_on_auth_failure response body: %s',
                     resp.text)
            self.assertEquals(400, resp.status_code)

    def test_delete_role_bad_state(self):
        with mock.patch.object(ResMgrMemProvider, 'delete_role') as delete_role:
            delete_role.side_effect = RoleUpdateConflict('conflict!')
            resp = self.app.delete('/v1/hosts/rsc_1/roles/test-role',
                                   expect_errors=True)
            LOG.info('test_delete_role_bad_state response body: %s', resp.text)
            self.assertEquals(409, resp.status_code)

    def test_delete_role_on_deauth_failure(self):
        with mock.patch.object(ResMgrMemProvider, 'delete_role') as delete_role:
            delete_role.side_effect = DuConfigError('error!')
            resp = self.app.delete('/v1/hosts/rsc_1/roles/test-role',
                                   expect_errors=True)
            LOG.info('test_delete_role_on_deauth_failure response body: %s',
                     resp.text)
            self.assertEquals(400, resp.status_code)

    def test_delete_host_bad_state(self):
        with mock.patch.object(ResMgrMemProvider, 'delete_host') as delete_role:
            delete_role.side_effect = RoleUpdateConflict('conflict!')
            resp = self.app.delete('/v1/hosts/rsc_1', expect_errors=True)
            LOG.info('test_delete_host_bad_state response body: %s', resp.text)
            self.assertEquals(409, resp.status_code)

    def test_delete_host_on_deauth_failure(self):
        with mock.patch.object(ResMgrMemProvider, 'delete_host') as delete_role:
            delete_role.side_effect = DuConfigError('error!')
            resp = self.app.delete('/v1/hosts/rsc_1', expect_errors=True)
            LOG.info('test_delete_host_on_deauth_failure response body: %s',
                     resp.text)
            self.assertEquals(400, resp.status_code)
