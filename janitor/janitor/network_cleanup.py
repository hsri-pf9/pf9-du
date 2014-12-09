#
# Copyright (c) 2014, Platform9 Systems.
# All rights reserved.
#
__author__ = 'Platform9'


import requests
import logging
from janitor import utils
from janitor.base import Base

LOG = logging.getLogger('janitor-daemon')

class NetworkCleanup(Base):
    """
    Perform network cleanup
    """

    def __init__(self, conf):
        super(NetworkCleanup, self).__init__(conf)

    def cleanup(self):
        token, project_id = utils.get_auth_token(self._auth_tenant,
                                                 self._auth_user,
                                                 self._auth_pass)
        resp = self._nova_request('os-networks', token, project_id)

        if not resp:
            LOG.info('No response')
            return

        network_json = resp.json()
        if not 'networks' in network_json:
            LOG.info('No nova networks found, ignoring')
            return

        network_uuids = set([n['id'] for n in network_json['networks']])

        host_networks = set()

        resp = self._nova_request('os-hypervisors/detail', token, project_id)

        if resp:
            hypervisor_json = resp.json()
            if 'hypervisors' in hypervisor_json:
                for h in hypervisor_json['hypervisors']:
                    host_nets = h['OS-EXT-PF9-HYP-ATTR:networks']
                    for n in host_nets:
                        host_networks.add(n['uuid'])

        dangling_networks = network_uuids - host_networks

        for n in dangling_networks:
            # This network should be cleaned up
            LOG.info('Network {net} has no hosts associated with it, cleaning up'.format(net=n))
            resp = self._nova_request('os-networks/{id}/action'.format(id=n), token,
                                      project_id, req_type='post',
                                      json_body={'disassociate': None})
            if not resp or resp.status_code not in (requests.codes.ok, 204, 202):
                LOG.error('Skipping network deletion')
                continue

            resp = self._nova_request('os-networks/{id}'.format(id=n), token, project_id,
                                      req_type='delete')
            if resp.status_code != requests.codes.ok:
                LOG.error('Network deletion failed for network {net}'.format(net=n))



