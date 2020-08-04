#
# Copyright (c) Platform9 Systems. All rights reserved
#

import logging
import requests

from keystoneauth1.identity import v3
from keystoneauth1 import session

LOG = logging.getLogger(__name__)


def get_session(conf):
    auth = v3.Password(
        auth_url=conf.get("keystone_authtoken", "auth_url"),
        username=conf.get("keystone_authtoken", "username"),
        password=conf.get("keystone_authtoken", "password"),
        project_name=conf.get("keystone_authtoken", "project_name"),
        user_domain_id=conf.get("keystone_authtoken", "user_domain_id"),
        project_domain_id=conf.get("keystone_authtoken", "project_domain_id"))
    sess = session.Session(auth=auth)
    return sess


def get_resmgr_hosts(resmgr_url, token):
    url = '/'.join([resmgr_url, 'v1', 'hosts'])
    headers = {'X-Auth-Token': token, 'Content-Type': 'application/json'}

    resp = requests.get(url, verify=False, headers=headers)

    if resp.status_code not in (requests.codes.ok, 204):
        LOG.error('Resource manager query failed: %d', resp.status_code)

    return resp

def get_resmgr_host_roles(resmgr_url, token, resmgr_host):
    url = '/'.join([resmgr_url, 'v1', 'hosts', resmgr_host])
    headers = {'X-Auth-Token': token, 'Content-Type': 'application/json'}

    resp = requests.get(url, verify=False, headers=headers)

    if resp.status_code not in (requests.codes.ok, 204):
        LOG.error('Resource manager query failed: %d', resp.status_code)
        return []
    return resp.json()["roles"]

def get_ostackhost_role_data(resmgr_hosts, resmgr_url, token):
    roles_to_look_for = set(['pf9-ostackhost-vmw', 'pf9-ostackhost-neutron-vmw'])
    headers = {'X-Auth-Token': token, 'Content-Type': 'application/json'}
    clusters = []
    for resmgr_host in resmgr_hosts:
        url = '/'.join([resmgr_url, 'v1', 'hosts', resmgr_host])
        resp = requests.get(url, verify=False, headers=headers)

        if resp.status_code not in (requests.codes.ok, 204):
            LOG.error('Resource manager query failed for host: %s with status: %d',
                                                    resmgr_host, resp.status_code)
        else:
            authed_roles = resp.json()['roles']
            ostackhost_present = roles_to_look_for.intersection(authed_roles)
            if len(ostackhost_present) == 1:
                url = '/'.join([resmgr_url, 'v1', 'hosts', resmgr_host,
                               'roles', ostackhost_present.pop()])
                resp = requests.get(url, verify=False, headers=headers)
                clusters.extend(resp.json()['cluster_name'].split(','))
            else:
                LOG.error('Resource manager query for host: %s returned more '
                          'than one ostackhost roles authorized. Taking none '
                          'in consideration.', resmgr_host)
    return clusters
