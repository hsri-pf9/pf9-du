#
# Copyright (c) 2014 Platform9 Systems.
# All rights reserved
#

__author__ = 'Platform9'

import json
import requests
import logging
import utils
from base import NovaBase


LOG = logging.getLogger('janitor-daemon')


class NovaCleanup(NovaBase):
    """
    Perform maintenance tasks for Nova
    """

    def __init__(self, conf):
        super(NovaCleanup, self).__init__(conf)
        self._resmgr_url = conf.get('resmgr', 'endpointURI')
        self._token = utils.get_auth_token(self._auth_tenant,
                                           self._auth_user,
                                           self._auth_pass,
                                           None)

    def cleanup(self):
        """Remove hypervisor and instance information from Nova for
        hosts which have been removed from resmgr
        """
        self._token = utils.get_auth_token(self._auth_tenant,
                                           self._auth_user,
                                           self._auth_pass,
                                           self._token)
        token_id = self._token['id']
        project_id = self._token['tenant']['id']

        def get_affected_instances(nova_only_ids):
            server_list = dict((nova_id, []) for nova_id in nova_only_ids)
            resp = self._nova_request('servers/detail?all_tenants=1', token_id, project_id)
            if resp.status_code != requests.codes.ok:
                LOG.error('Unexpected response {code} while querying servers', dict(code=resp.status_code))
                raise RuntimeError('code=%d' % resp.status_code)

            for server in resp.json()['servers']:
                if server['OS-EXT-SRV-ATTR:host'] in nova_only_ids:
                    LOG.info('Server %(uuid)s is on affected hypervisor, adding to cleanup list',
                             dict(uuid=server['id']))
                    server_list[server['OS-EXT-SRV-ATTR:host']].append(server['id'])
            return server_list

        def get_host_to_aggr_map(nova_only_ids):
            host_to_aggr = dict((nova_id, []) for nova_id in nova_only_ids)
            resp = self._nova_request('os-aggregates', token_id, project_id)
            if resp.status_code != requests.codes.ok:
                LOG.error('Unexpected response {code} while querying aggregates', dict(code=resp.status_code))
                raise RuntimeError('code=%d' % resp.status_code)

            for aggr in resp.json()['aggregates']:
                aggr_hosts = aggr['hosts']
                for aggr_host in aggr_hosts:
                    if aggr_host in nova_only_ids:
                        host_to_aggr[aggr_host].append(aggr['id'])

            return host_to_aggr

        def cleanup_servers(server_list):
            for srv_id in server_list:
                LOG.info('Cleaning up instance {server_id} from nova'.format(server_id=srv_id))
                resp = self._nova_request('servers/{id}'.format(id=srv_id),
                                          token_id, project_id, req_type='delete')

                if resp.status_code not in (requests.codes.ok, requests.codes.no_content):
                    raise RuntimeError('Unexpected error code: {code} when deleting instance'
                                       .format(code=resp.status_code))

        def cleanup_hosts(nova_id, pf9_id, host_aggr_map):
            LOG.info('Cleaning up hypervisor info for %s', pf9_id)
            # Remove host from all aggregates
            if pf9_id in host_aggr_map:
                for aggr_id in host_aggr_map[pf9_id]:
                    LOG.info('Removing host {host_id} from aggregate {aggr_id}'.format(host_id=pf9_id, aggr_id=aggr_id))
                    resp = self._nova_request('os-aggregates/%s/action' % aggr_id,
                                              token_id, project_id,
                                              json_body={'remove_host': {'host': pf9_id}},
                                              req_type='post')
                    if resp.status_code != requests.codes.ok:
                        LOG.error('Unexpected response code %d when removing host: %s from'
                                  ' aggregate: %d', resp.status_code, pf9_id, aggr_id)
                        raise RuntimeError('code=%d' % resp.status_code)

            # Delete nova-compute service for this host from nova.
            # TODO: handle neutron agents cleanup
            resp = self._nova_request('os-services', token_id, project_id)
            if resp.status_code != requests.codes.ok:
                raise RuntimeError('Unexpected response code %d when querying all services', resp.status_code)
            LOG.debug('queried os-services: %s', resp.json())
            for service in resp.json()['services']:
                if service['binary'] == 'nova-compute' and service['host'] == pf9_id:
                    LOG.info('deleting os-service %s', service['id'])
                    resp = self._nova_request('os-services/%s' % service['id'],
                                              token_id, project_id, req_type='delete')
                    if resp.status_code != requests.codes.no_content:
                        raise RuntimeError('Unexpected error code: {code} when deleting compute service'
                            .format(code=resp.status_code))
                    break

        def find_nova_hosts_not_in_resmgr(resmgr_ids, token, project_id):
            resp = self._nova_request('os-hypervisors/detail', token, project_id)

            if resp.status_code != requests.codes.ok:
                raise RuntimeError('Unexpected return code: {code} when '
                                   'querying hypervisors'.format(code=resp.status_code))

            nova_data = resp.json()['hypervisors']
            nova_map = dict()
            nova_ids = set()

            if not is_vmware:
                for host in nova_data:
                    nova_map[host['OS-EXT-PF9-HYP-ATTR:host_id']] = host['id']
                    nova_ids.add(host['OS-EXT-PF9-HYP-ATTR:host_id'])
            else:
                clusters = utils.get_ostackhost_role_data(resmgr_ids,
                                                          self._resmgr_url,
                                                          token).split(',')
                for host in nova_data:
                    nova_map[host['OS-EXT-PF9-HYP-ATTR:host_id']] = host['id']
                    # Split the cluster name and verify as Hypervisor hostname is of format
                    # "domain-c86104(test_cluster)" and role data has just the cluster name
                    # "test_cluster".
                    if host['hypervisor_hostname'].split('(')[1].strip(')') not in clusters:
                        nova_ids.add(host['OS-EXT-PF9-HYP-ATTR:host_id'])
            return nova_ids.difference(resmgr_ids), nova_map

        # 1. Query resmgr hosts
        resp = utils.get_resmgr_hosts(self._resmgr_url, token_id)

        if resp.status_code != requests.codes.ok:
            LOG.error('Unexpected code {code} during authentication', dict(code=resp.status_code))
            return

        resmgr_data = resp.json()
        resmgr_kvm_ids = set(h['id'] for h in filter(lambda h:
                                'pf9-ostackhost' in h['roles'] or
                                'pf9-ostackhost-neutron' in h['roles'],
                                resmgr_data))

        resmgr_vmw_ids = set(h['id'] for h in filter(lambda h:
                                'pf9-ostackhost-vmw' in h['roles'] or
                                'pf9-ostackhost-neutron-vmw' in h['roles'],
                                resmgr_data))

        is_vmware = True if resmgr_vmw_ids else False

        # 2 & 3. Find all nova hosts and nova-only hosts that are not in resmgr
        try:
            nova_only_ids, nova_map = find_nova_hosts_not_in_resmgr(
                                            resmgr_kvm_ids | resmgr_vmw_ids,
                                            token_id, project_id)
        except Exception, e:
            LOG.error('Error finding nova hosts: %s', e)
            return

        host_to_aggr_map = get_host_to_aggr_map(nova_only_ids)

        # 4. Find instances on hypervisors TB removed
        try:
            server_list = get_affected_instances(nova_only_ids)
        except RuntimeError:
            LOG.error('Unexpected error while querying server information, aborting cleanup')
            return

        for pf9_id in nova_only_ids:
            # 5. Clean up hosts found in nova, but not with resmgr
            try:
                cleanup_hosts(nova_map[pf9_id], pf9_id, host_to_aggr_map)
            except:
                # cleanup hosts logs errors, so just return
                return

            # 6. Deleted affected servers
            try :
                LOG.info('Deleting all instances on hypervisor {host_id} from nova'.format(host_id=pf9_id))
                cleanup_servers(server_list[pf9_id])
            except RuntimeError as re:
                LOG.error('Unexpected error %(err)s, aborting cleanup', dict(err=re))
                return

