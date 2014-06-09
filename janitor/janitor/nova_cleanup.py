#
# Copyright (c) Platform9 Systems. All rights reserved
#

__author__ = 'Platform9'

import requests
import logging
from ConfigParser import ConfigParser
import json

LOG = logging.getLogger('janitor-daemon')


class NovaCleanup(object):
    """
    Perform maintenance tasks for Nova
    """

    def __init__(self, conf):
        self._resmgr_url = conf.get('resmgr', 'endpointURI')
        self._req_timeout = conf.get('DEFAULT', 'requestTimeout')
        self._wait = conf.get('DEFAULT', 'requestWaitPeriod')

        self._project_id = conf.get('PF9', 'pf9_project_id')
        self._user_id = conf.get('PF9', 'pf9_user_id')

        self._nova_url = conf.get('nova', 'endpointURI')
        self._nova_conf = NovaCleanup._parse_nova_conf(conf.get('nova', 'configfile'))

    @staticmethod
    def _parse_nova_conf(configfile):
        cfg = ConfigParser()
        cfg.read(configfile)

        nova_conf = dict()
        nova_conf['tenant'] = cfg.get('keystone_authtoken', 'admin_tenant_name')
        nova_conf['admin_name'] = cfg.get('keystone_authtoken', 'admin_user')
        nova_conf['password'] = cfg.get('keystone_authtoken', 'admin_password')

        return nova_conf

    @staticmethod
    def _get_auth_token(tenant, user, password):
        # FIXME: Make this reuse tokens
        data = {
            "auth": {
                "tenantName": tenant,
                "passwordCredentials": {
                    "username": user,
                    "password": password
                }
            }
        }

        url = 'http://localhost:35357/v2.0/tokens'

        r = requests.post(url, json.dumps(data), verify=False, headers={'Content-Type': 'application/json'})

        if r.status_code != requests.codes.ok:
            raise RuntimeError('Token request returned: %d' % r.status_code)

        return r.json()['access']['token']['id']

    def _nova_request(self, namespace, token, req_type='get', body=None):
        url = '/'.join([self._nova_url, 'v2', self._project_id, namespace])

        headers = {'X-Auth-Token': token, 'Content-Type': 'application/json'}

        assert(req_type in ('get', 'post', 'delete'))

        if req_type == 'get':
            resp = requests.get(url, verify=False, headers=headers)
        elif req_type == 'post':
            resp = requests.post(url, body, verify=False, headers=headers)
        elif req_type == 'delete':
            resp = requests.delete(url)

        if resp.status_code != requests.codes.ok:
            LOG.error('Nova hypervisor query failed: %d', resp.status_code)

        return resp

    def _resmgr_request(self, token):
        url = '/'.join([self._resmgr_url, 'v1', 'hosts'])
        headers = {'X-Auth-Token': token, 'Content-Type': 'application/json'}

        resp = requests.get(url, verify=False, headers=headers)

        if resp.status_code not in (requests.codes.ok, 204):
            LOG.error('Resource manager query failed: %d', resp.status_code)

        return resp

    def cleanup_hosts(self):
        """Remove hypervisor and instance information from Nova for
        hosts which have been removed from resmgr
        """
        token = NovaCleanup._get_auth_token(self._nova_conf['tenant'],
                                            self._nova_conf['admin_name'],
                                            self._nova_conf['password'])

        resp = self._resmgr_request(token)

        if resp.status_code != requests.codes.ok:
            return

        resmgr_data = resp.json()
        resmgr_ids = set(h['id'] for h in filter(lambda h: h['state'] == 'active', resmgr_data))
        resp = self._nova_request('os-hypervisors', token)

        if resp.status_code != requests.codes.ok:
            return

        nova_data = resp.json()['hypervisors']
        nova_ids = [h['id'] for h in nova_data]

        for nova_id in nova_ids:
            if nova_id not in resmgr_ids:
                LOG.info('Cleaning up hypervisor info for %s', nova_id)
                resp = self._nova_request('os-hypervisors/%s' % str(nova_id), token, req_type='delete')

                if resp.status_code != 204:
                    LOG.error('Skipping hypervisor %s', nova_id)

