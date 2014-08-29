#
# Copyright (c) Platform9 Systems. All rights reserved
#

__author__ = 'Platform9'

import requests
import logging
from janitor import utils

LOG = logging.getLogger('janitor-daemon')


class NovaCleanup(object):
    """
    Perform maintenance tasks for Nova
    """

    def __init__(self, conf):
        self._resmgr_url = conf.get('resmgr', 'endpointURI')
        self._req_timeout = conf.get('DEFAULT', 'requestTimeout')
        self._wait = conf.get('DEFAULT', 'requestWaitPeriod')
        self._nova_url = conf.get('nova', 'endpointURI')
        nova_config = conf.get('nova', 'configfile')
        self._auth_user, self._auth_pass, self._auth_tenant = \
                utils.get_keystone_credentials(nova_config)

    def _nova_request(self, namespace, token, proj_id, req_type='get'):
        url = '/'.join([self._nova_url, 'v2', proj_id, namespace])

        headers = {'X-Auth-Token': token, 'Content-Type': 'application/json'}

        assert(req_type in ('get', 'delete'))

        resp = None

        if req_type == 'get':
            resp = requests.get(url, verify=False, headers=headers)
        elif req_type == 'delete':
            resp = requests.delete(url, verify=False, headers=headers)

        if not resp:
            LOG.error("No response")
        elif resp.status_code not in (requests.codes.ok, 204):
            LOG.error('Nova hypervisor query failed: %d', resp.status_code)

        return resp

    def cleanup(self):
        """Remove hypervisor and instance information from Nova for
        hosts which have been removed from resmgr
        """
        token, project_id = utils.get_auth_token(self._auth_tenant,
                                                 self._auth_user,
                                                 self._auth_pass)

        resp = utils.get_resmgr_hosts(self._resmgr_url, token)

        if resp.status_code != requests.codes.ok:
            return

        resmgr_data = resp.json()
        resmgr_ids = set(h['id'] for h in filter(lambda h: h['state'] == 'active', resmgr_data))

        resp = self._nova_request('os-hypervisors/detail', token, project_id)

        if resp.status_code != requests.codes.ok:
            return

        nova_data = resp.json()['hypervisors']
        nova_map = dict()
        nova_ids = set()
        for h in nova_data:
            nova_map[h['OS-EXT-PF9-HYP-ATTR:host_id']] = h['id']
            nova_ids.add(h['OS-EXT-PF9-HYP-ATTR:host_id'])

        nova_only_ids = nova_ids.difference(resmgr_ids)

        # Clean up hosts found in nova, but not with resmgr
        for pf9_id in nova_only_ids:
            LOG.info('Cleaning up hypervisor info for %s', pf9_id)
            resp = self._nova_request('os-hypervisors/%s' % str(nova_map[pf9_id]), token, project_id,
                                          req_type='delete')

            if resp.status_code != 204:
                LOG.error('Skipping hypervisor %s, resp: %d', pf9_id, resp.status_code)

