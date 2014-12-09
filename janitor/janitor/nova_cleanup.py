#
# Copyright (c) 2014 Platform9 Systems.
# All rights reserved
#

__author__ = 'Platform9'

import requests
import logging
from janitor import utils
from janitor.base import Base

LOG = logging.getLogger('janitor-daemon')


class NovaCleanup(Base):
    """
    Perform maintenance tasks for Nova
    """

    def __init__(self, conf):
        super(NovaCleanup, self).__init__(conf)
        self._resmgr_url = conf.get('resmgr', 'endpointURI')

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

