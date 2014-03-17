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
        self.admin_response['access']['token']['id'] = self.admin_token
        self.admin_response['access']['token']['expires'] = tomorrow.isoformat()
        self.admin_response['access']['user']['roles'].append({'name' : 'hostadmin'})

        # autherticated with user
        self.user_token = 'usertoken'
        self.user_response = deepcopy(responses['good'])
        self.user_response['access']['token']['id'] = self.user_token
        self.user_response['access']['token']['expires'] = tomorrow.isoformat()

        # not authenticated
        self.unauth_token = 'unauthtoken'
        self.unauth_response = responses['bad']

    def setUp(self):
        paste_ini = os.path.abspath(
                os.path.join(self.this_dir, '..', '..', 'resmgr-paste.ini'))

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

    def mock_keystone(self, token_id, status, response_dict) :
        """
        Setup the keystone mock. Must be called under an httpretty.activate
        decorator
        """
        httpretty.register_uri(httpretty.GET,
                               "http://127.0.0.1:35357/",
                               status = 300,
                               body = self.keystone_versions,
                               content_type="application/json")

        httpretty.register_uri(httpretty.GET,
                               "http://127.0.0.1:35357/v2.0/tokens/%s" % token_id,
                               status = status,
                               body = json.dumps(response_dict),
                               content_type="application/json")

    @httpretty.activate
    def test_roles_get(self) :
        # non-admin auth
        self.mock_keystone(self.user_token, 200, self.user_response)
        response = self.app.get('/v1/roles', {}, {'X-Auth-Token': self.user_token})
        self.assertEquals(200, response.status_code)
        body = json.loads(response.text)
        self.assertEquals("pf9-ostackhost", body[0]['id'])

        # bad auth
        self.mock_keystone(self.unauth_token, 404, self.unauth_response)
        response = self.app.get('/v1/roles', {},
                {'X-Auth-Token': self.unauth_token}, expect_errors = True)
        self.assertEquals(401, response.status_code)

    @httpretty.activate
    def test_resource_get(self) :
        # non-admin auth
        self.mock_keystone(self.user_token, 200, self.user_response)
        response = self.app.get('/v1/resources', {}, {'X-Auth-Token': self.user_token})
        self.assertEquals(200, response.status_code)
        body = json.loads(response.text)
        self.assertTrue(0 < len([res for res in body if res['id'] == 'rsc_1']))

        # bad auth
        self.mock_keystone(self.unauth_token, 404, self.unauth_response)
        response = self.app.get('/v1/resources', {},
                {'X-Auth-Token': self.unauth_token}, expect_errors = True)
        self.assertEquals(401, response.status_code)


    @httpretty.activate
    def test_roles_put_then_delete(self) :
        # PUT
        # non-admin auth
        self.mock_keystone(self.user_token, 200, self.user_response)
        response = self.app.put('/v1/resources/rsc_1/roles/pf9-ostackhost', {},
                {'X-Auth-Token': self.user_token}, expect_errors = True)
        self.assertEquals(403, response.status_code)

        # bad auth
        self.mock_keystone(self.unauth_token, 404, self.unauth_response)
        response = self.app.put('/v1/resources/rsc_1/roles/pf9-ostackhost', {},
                {'X-Auth-Token': self.unauth_token}, expect_errors = True)
        self.assertEquals(401, response.status_code)

        # admin auth
        self.mock_keystone(self.admin_token, 200, self.admin_response)
        response = self.app.put('/v1/resources/rsc_1/roles/pf9-ostackhost', {},
                {'X-Auth-Token': self.admin_token})
        self.assertEquals(200, response.status_code)
        response = self.app.get('/v1/resources/rsc_1/', {},
                {'X-Auth-Token': self.admin_token})
        self.assertEquals(200, response.status_code)
        body = json.loads(response.text)
        self.assertTrue('pf9-ostackhost' in body['roles'])

        # DELETE
        # non-admin auth
        self.mock_keystone(self.user_token, 200, self.user_response)
        response = self.app.delete('/v1/resources/rsc_1/roles/pf9-ostackhost', {},
                {'X-Auth-Token': self.user_token}, expect_errors = True)
        self.assertEquals(403, response.status_code)

        # bad auth
        self.mock_keystone(self.unauth_token, 404, self.unauth_response)
        response = self.app.delete('/v1/resources/rsc_1/roles/pf9-ostackhost', {},
                {'X-Auth-Token': self.unauth_token}, expect_errors = True)
        self.assertEquals(401, response.status_code)

        # admin auth
        self.mock_keystone(self.admin_token, 200, self.admin_response)
        response = self.app.delete('/v1/resources/rsc_1/roles/pf9-ostackhost', {},
                {'X-Auth-Token': self.admin_token})
        self.assertEquals(200, response.status_code)
        response = self.app.get('/v1/resources/rsc_1/', {},
                {'X-Auth-Token': self.admin_token})
        self.assertEquals(200, response.status_code)
        body = json.loads(response.text)
        self.assertTrue('pf9-ostackhost' not in body['roles'])

if __name__ == '__main__':
    unittest.main()


