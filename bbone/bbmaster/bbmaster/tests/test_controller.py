from unittest import TestCase
from webtest import TestApp
from bbmaster.tests import FunctionalTest
import os
from pecan import set_config
from pecan.testing import load_test_app

from bbmaster import bbone_provider_memory

import mock_data


class TestRootController(FunctionalTest):

    def setUp(self):
        self.app = load_test_app(os.path.join(
            os.path.dirname(__file__),
            'controller_config.py'
        ))
        bbone_provider_memory.provider.load_test_data(mock_data.data)


    def tearDown(self):
        set_config({}, overwrite=True)

    def test_get_not_found(self):
        # Bad host IDs should return error response
        response = self.app.get('/v1/hosts/231', expect_errors=True)
        assert response.status_int == 404

    def test_get_host_details(self):
        # Get host IDs
        response = self.app.get('/v1/hosts/')
        body = response.json_body
        assert type(body) is list
        assert body[0]['host_id'] == '468860b4-8a16-11e3-909d-005056a93468'
        assert body[1]['host_id'] == '2d734f3a-8a16-11e3-909d-005056a93468'

        assert body[1]['apps']['service1']['running']
        assert body[1]['apps']['service1']['version'] == '1.1'

    def test_get_host_ids(self):
        response = self.app.get('/v1/hosts/ids')
        body = response.json_body
        assert type(body) is list
        assert body[0] == '468860b4-8a16-11e3-909d-005056a93468'
        assert body[1] == '2d734f3a-8a16-11e3-909d-005056a93468'

    def test_get_apps_config(self):
        url = '/v1/hosts/468860b4-8a16-11e3-909d-005056a93468/apps'
        response = self.app.get(url)
        body = response.json_body
        assert type(body) is dict
        assert body['service2']['config']['z'] == 300

    def test_put_config(self):
        url = '/v1/hosts/468860b4-8a16-11e3-909d-005056a93468/apps'
        self.app.put_json(url, { 't': 'foo', 's': 'bar'})
        url = '/v1/hosts/468860b4-8a16-11e3-909d-005056a93468'
        # Read back host and make sure desired_apps is not exposed
        response = self.app.get(url)
        body = response.json_body
        assert body['host_id'] == '468860b4-8a16-11e3-909d-005056a93468'
        assert 'apps' in body
        assert 'desired_apps' not in body

    def test_put_missing(self):
        url = '/v1/hosts/missingid/apps'
        self.app.put_json(url, { 'a': 'foo', 'b': 'bar'})
        url = '/v1/hosts/missingid'
        body = self.app.get(url).json_body
        assert isinstance(body, dict)
        assert body['host_id'] == 'missingid'
        assert body['status'] == 'missing'
        assert 'info' not in body
        assert 'apps' not in body


