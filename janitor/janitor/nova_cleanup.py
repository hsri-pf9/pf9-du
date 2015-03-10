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

        def get_host_to_aggr_map(nova_only_ids):
            host_to_aggr = dict((nova_id, []) for nova_id in nova_only_ids)
            resp = self._nova_request('os-aggregates', token, project_id)
            if resp.status_code != requests.codes.ok:
                return host_to_aggr

            for aggr in resp.json()['aggregates']:
                aggr_hosts = aggr['hosts']
                for aggr_host in aggr_hosts:
                    if aggr_host in nova_only_ids:
                        host_to_aggr[aggr_host].append(aggr['id'])

            return host_to_aggr

        def cleanup_hosts(nova_id, pf9_id, host_aggr_map):
            LOG.info('Cleaning up hypervisor info for %s', pf9_id)
            # Remove host from all aggregates
            if pf9_id in host_aggr_map:
                for aggr_id in host_aggr_map[pf9_id]:
                    resp = self._nova_request('os-aggregates/%s/action' % aggr_id,
                                              token, project_id,
                                              json_body={'remove_host': {'host': pf9_id}},
                                              req_type='post')
                    if resp.status_code != requests.codes.ok:
                        LOG.error('Unexpected response code %d when removing host: %s from'
                                  ' aggregate: %d', resp.status_code, pf9_id, aggr_id)
                        return

            # Remove hypervisor from nova.
            resp = self._nova_request('os-hypervisors/%s' % str(nova_id), token, project_id,
                                      req_type='delete')

            if resp.status_code != 204:
                LOG.error('Skipping hypervisor %s, resp: %d', pf9_id, resp.status_code)

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

        host_to_aggr_map = get_host_to_aggr_map(nova_only_ids)
        # Clean up hosts found in nova, but not with resmgr
        for pf9_id in nova_only_ids:
            cleanup_hosts(nova_map[pf9_id], pf9_id, host_to_aggr_map)


