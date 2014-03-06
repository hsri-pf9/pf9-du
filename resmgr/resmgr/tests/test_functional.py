from resmgr.tests import FunctionalTest
from resmgr.resmgr_provider import RState


class TestResMgr(FunctionalTest):

    def _get_roles(self):
        response = self.app.get('/v1/roles')
        assert response is not None
        return response.json_body

    def _get_resources(self):
        response = self.app.get('/v1/resources')
        assert response is not None
        return response.json_body

    def _get_one_res(self, id):
        response = self.app.get(''.join(['/v1/resources/',
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
            role = self._get_single_role(item['id'])
            assert role is not None

    def test_non_existing_data(self):
        fake_keys = ['dhfjshdkf', 'fhshfs']

        for fake in fake_keys:
            for path in ['/v1/resources/', '/v1/roles/']:
                response = self.app.get(''.join([path,
                                                 fake]), expect_errors=True)
                assert response.status_int == 404

    def test_get_resources(self):
        res = self._get_resources()
        assert type(res) is list
        assert len(res)

    def test_associate(self):
        roles = [r['id'] for r in self._get_roles()]
        res = self._get_resources()

        for (k1, k2) in zip(res, roles):
            k1_id = k1['id']
            self.app.put(''.join(['/v1/resources/', k1_id, '/roles/', k2]))
            one_res = self._get_one_res(k1_id)

            assert one_res['state'] == RState.active

            self.app.delete(''.join(['/v1/resources/', k1_id, '/roles/', k2]))

            one_res = self._get_one_res(k1_id)

            assert one_res['state'] == RState.inactive

    def test_put_config(self):
        #TODO: Figure out how to test put operations
        pass
