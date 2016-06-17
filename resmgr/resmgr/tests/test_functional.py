from resmgr.tests import FunctionalTest


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
