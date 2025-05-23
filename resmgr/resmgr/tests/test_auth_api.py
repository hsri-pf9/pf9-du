# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights reserved

from copy import deepcopy
from datetime import datetime, timedelta
import httpretty
import json
import paste.deploy
from pecan import set_config
import os.path
import unittest
import webtest

class TestAuthApi(unittest.TestCase) :

    def __init__(self, *args, **kwargs):
        super(TestAuthApi, self).__init__(*args, **kwargs)
        self.this_dir = os.path.dirname(__file__)

        # data for fake keystone
        with open(os.path.join(self.this_dir, 'keystone-responses.json')) as f :
            responses = json.load(f)

        tomorrow = datetime.now() + timedelta(days = 1)

        # authenticated with admin
        self.admin_token = 'admintoken'
        self.admin_response = deepcopy(responses['good'])
        self.admin_response['token']['expires_at'] = tomorrow.isoformat()

        # authenticated with user, _member_ role only
        self.user_token = 'usertoken'
        self.user_response = deepcopy(responses['good'])
        self.user_response['token']['expires_at'] = tomorrow.isoformat()
        self.user_response['token']['roles'] = \
            [r for r in self.user_response['token']['roles']
             if r['name'] == '_member_']

        # not authenticated
        self.unauth_token = 'unauthtoken'
        self.unauth_response = responses['bad']

    def setUp(self):
        paste_ini = os.path.abspath(
                os.path.join(self.this_dir, 'resmgr-paste.ini'))

        # create the app with the paste config. This should enable auth
        # enforcement, even though config.py specifies enforce = false
        paste_app = paste.deploy.loadapp('config:%s' % paste_ini,
                global_conf = {'config' : os.path.join(self.this_dir, 'config.py')})

        self.app = webtest.TestApp(paste_app)

        # middleware makes calls to keystone for version info
        with open(os.path.join(self.this_dir, 'keystone-versions.json')) as g :
            self.keystone_versions = g.read()

    def tearDown(self):
        set_config({}, overwrite = True)

    def mock_keystone(self, token_id, status, response_dict, response_headers=None) :
        """
        Setup the keystone mock. Must be called under an httpretty.activate
        decorator
        """
        httpretty.register_uri(httpretty.GET,
                               "http://127.0.0.1:5000/",
                               status = 300,
                               body = self.keystone_versions,
                               content_type="application/json")

        httpretty.register_uri(httpretty.GET,
                               "http://127.0.0.1:5000/v3/auth/tokens",
                               status = status,
                               body = json.dumps(response_dict),
                               content_type="application/json")

        httpretty.register_uri(httpretty.POST,
                               "http://127.0.0.1:5000/v3/auth/tokens",
                               status = status,
                               body = json.dumps(response_dict),
                               adding_headers = response_headers, 
                               content_type="application/json")


    @httpretty.activate
    def test_roles_get(self) :
        # non-admin auth
        self.mock_keystone(self.user_token, 200, self.user_response, {'X-Subject-Token': self.user_token})
        response = self.app.get('/v1/roles', {}, {'X-Auth-Token': self.user_token})
        self.assertEqual(200, response.status_code)
        body = json.loads(response.text)
        self.assertEqual("pf9-ostackhost", body[0]['name'])

        # bad auth
        self.mock_keystone(self.unauth_token, 404, self.unauth_response)
        response = self.app.get('/v1/roles', {},
                {'X-Auth-Token': self.unauth_token}, expect_errors = True)
        self.assertEqual(401, response.status_code)

    @httpretty.activate
    def test_host_get(self) :
        # non-admin auth
        self.mock_keystone(self.user_token, 200, self.user_response, {'X-Subject-Token': self.user_token})
        response = self.app.get('/v1/hosts', {}, {'X-Auth-Token': self.user_token})
        self.assertEqual(200, response.status_code)
        body = json.loads(response.text)
        self.assertTrue(0 < len([host for host in body if host['id'] == 'rsc_1']))

        # bad auth
        self.mock_keystone(self.unauth_token, 404, self.unauth_response)
        response = self.app.get('/v1/hosts', {},
                {'X-Auth-Token': self.unauth_token}, expect_errors = True)
        self.assertEqual(401, response.status_code)


    @httpretty.activate
    def test_roles_put_then_delete(self) :
        # PUT
        # non-admin auth
        self.mock_keystone(self.user_token, 200, self.user_response, {'X-Subject-Token': self.user_token})
        response = self.app.put('/v1/hosts/rsc_1/roles/pf9-ostackhost', {},
                {'X-Auth-Token': self.user_token}, expect_errors = True)
        self.assertEqual(403, response.status_code)

        # bad auth
        self.mock_keystone(self.unauth_token, 404, self.unauth_response)
        response = self.app.put('/v1/hosts/rsc_1/roles/pf9-ostackhost', {},
                {'X-Auth-Token': self.unauth_token}, expect_errors = True)
        self.assertEqual(401, response.status_code)

        # admin auth
        self.mock_keystone(self.admin_token, 200, self.admin_response, {'X-Subject-Token': self.admin_token})
        response = self.app.put('/v1/hosts/rsc_1/roles/pf9-ostackhost', {},
                {'X-Auth-Token': self.admin_token})
        self.assertEqual(200, response.status_code)
        response = self.app.get('/v1/hosts/rsc_1/', {},
                {'X-Auth-Token': self.admin_token})
        self.assertEqual(200, response.status_code)
        body = json.loads(response.text)
        self.assertTrue('pf9-ostackhost' in body['roles'])

        # DELETE
        # non-admin auth
        self.mock_keystone(self.user_token, 200, self.user_response)
        response = self.app.delete('/v1/hosts/rsc_1/roles/pf9-ostackhost', {},
                {'X-Auth-Token': self.user_token}, expect_errors = True)
        self.assertEqual(403, response.status_code)

        # bad auth
        self.mock_keystone(self.unauth_token, 404, self.unauth_response)
        response = self.app.delete('/v1/hosts/rsc_1/roles/pf9-ostackhost', {},
                {'X-Auth-Token': self.unauth_token}, expect_errors = True)
        self.assertEqual(401, response.status_code)

        # admin auth
        self.mock_keystone(self.admin_token, 200, self.admin_response)
        response = self.app.delete('/v1/hosts/rsc_1/roles/pf9-ostackhost', {},
                {'X-Auth-Token': self.admin_token})
        self.assertEqual(200, response.status_code)
        response = self.app.get('/v1/hosts/rsc_1/', {},
                {'X-Auth-Token': self.admin_token})
        self.assertEqual(200, response.status_code)
        body = json.loads(response.text)
        self.assertTrue('pf9-ostackhost' not in body['roles'])

if __name__ == '__main__':
    unittest.main()
