#
# Copyright (c) 2014, Platform9 Systems.
# All rights reserved.
#

import exceptions
import requests
import logging
import utils
from base import NovaBase

__author__ = 'Platform9'

LOG = logging.getLogger('janitor-daemon')


class InvalidResponse(exceptions.Exception):
    def __init__(self, message, errors=None):
        super(InvalidResponse, self).__init__(message, errors)


class NetworkCleanup(NovaBase):
    """
    Perform network cleanup
    """

    def __init__(self, conf):
        super(NetworkCleanup, self).__init__(conf)
        self._token = utils.get_auth_token(self._auth_tenant,
                                           self._auth_user,
                                           self._auth_pass,
                                           None)

    def build_instance_network_mapping(self,  token_id, project_id, network_ids):
        """
        Figure out which interfaces are connected to networks
        about to be removed.
        :param token:
        :param project_id:
        :param network_ids: Dangling networks to be removed
        :return:
        """
        resp = self._nova_request('servers?all_tenants=1', token_id, project_id)
        if resp.status_code != requests.codes.ok:
            LOG.error('Received response: {code}, skipping network cleanup'.
                      format(code=resp.status_code))
            raise InvalidResponse('No virtual machines found, invalid response {code}'.
                                  format(code=resp.status_code))
        instance_ids = [s['id'] for s in resp.json()['servers']]
        network_to_inst = dict((net_id, []) for net_id in network_ids)

        for instance_id in instance_ids:
            LOG.info('Querying interfaces for {server_id}'.format(server_id=instance_id))
            resp = self._nova_request('servers/{srv_id}/os-virtual-interfaces'.
                                      format(srv_id=instance_id),
                                      token_id, project_id)
            if resp.status_code != requests.codes.ok:
                msg = '[VIF query] Received response: {code}'.\
                    format(code=resp.status_code)
                LOG.error(msg)
                raise InvalidResponse(msg)
            if 'virtual_interfaces' in resp.json():
                vif_infos = resp.json()['virtual_interfaces']
                for vif_info in vif_infos:
                    if 'OS-EXT-VIF-NET:net_id' in vif_info and \
                                    vif_info['OS-EXT-VIF-NET:net_id'] in \
                                    network_to_inst:
                        network_to_inst[vif_info['OS-EXT-VIF-NET:net_id']]\
                            .append((instance_id, vif_info['id']))

        return network_to_inst

    def cleanup(self):
        self._token = utils.get_auth_token(self._auth_tenant,
                                           self._auth_user,
                                           self._auth_pass,
                                           self._token)
        token_id = self._token['id']
        project_id = self._token['tenant']['id']
        resp = self._nova_request('os-networks', token_id, project_id)

        if not resp:
            LOG.error('No response when querying networks')
            return

        network_json = resp.json()
        if 'networks' not in network_json:
            LOG.info('No nova networks found, ignoring')
            return

        network_uuids = set([n['id'] for n in network_json['networks']])

        host_networks = set()

        resp = self._nova_request('os-hypervisors/detail', token_id, project_id)

        if not resp or resp.status_code != requests.codes.ok:
            status_code = 'Null Resp' if not resp else str(resp.status_code)
            msg = '[Network cleanup] Error querying hypervisors. Response code {code}'.format(code=status_code)
            LOG.error(msg)
            return

        hypervisor_json = resp.json()
        if 'hypervisors' in hypervisor_json:
            for h in hypervisor_json['hypervisors']:
                host_nets = h['OS-EXT-PF9-HYP-ATTR:networks']
                for n in host_nets:
                    host_networks.add(n['uuid'])

        dangling_networks = network_uuids - host_networks

        if not dangling_networks:
            return

        try:
            net_to_inst = self.build_instance_network_mapping(token_id,
                                                              project_id, dangling_networks)
        except InvalidResponse as ie:
            LOG.error('{msg}'.format(msg=ie))
            return

        for n in dangling_networks:
            # This network should be cleaned up

            # 1. Remove all VIF records
            for inst_id, vif_id in net_to_inst[n]:
                body = dict(removeVif=vif_id)
                resp = self._nova_request('servers/{srv_id}/action'.
                                          format(srv_id=inst_id), token_id,
                                          project_id, req_type='post', json_body=body)
                if resp.status_code not in (requests.codes.ok, 202):
                    LOG.error('Error cleaning up VIF record {vif} from instance {inst},'
                              'status: {stat}'
                              .format(vif=vif_id, inst=inst_id, stat=resp.status_code))
                    return

            # 2. Remove all fixed IPs associated with the network
            resp = self._nova_request('os-networks/{id}/action'.format(id=n), token_id,
                                      project_id, req_type='post',
                                      json_body={'deleteFixedIPs': None})
            if resp.status_code not in (requests.codes.ok, 202):
                LOG.error('Error removing fixed IPs from network {net}, status: {code}'
                          .format(net=n, code=resp.status_code))
                continue

            # 3. Remove the network
            LOG.info('Network {net} has no hosts associated with it, cleaning up'
                     .format(net=n))
            resp = self._nova_request('os-networks/{id}/action'.format(id=n), token_id,
                                      project_id, req_type='post',
                                      json_body={'disassociate': None})
            if resp.status_code not in (requests.codes.ok, 204, 202):
                LOG.error('Skipping network deletion, return code {code}'
                          .format(code=resp.status_code))
                continue

            resp = self._nova_request('os-networks/{id}'.format(id=n), token_id, project_id,
                                      req_type='delete')
            if resp.status_code not in (requests.codes.ok, 202):
                LOG.error('Network deletion failed for network {net}'.format(net=n))



