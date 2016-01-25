#
# Copyright (c) Platform9 Systems. All rights reserved
#

import json
import logging
import requests

from ConfigParser import ConfigParser
import time

LOG = logging.getLogger('janitor-daemon')


def _get_auth_token(tenant, user, password):
    data = {
        "auth": {
            "tenantName": tenant,
            "passwordCredentials": {
                "username": user,
                "password": password
            }
        }
    }

    url = 'http://localhost:8080/keystone/v2.0/tokens'

    r = requests.post(url, json.dumps(data),
                      verify=False, headers={'Content-Type': 'application/json'})

    if r.status_code != requests.codes.ok:
        raise RuntimeError('Token request returned: %d' % r.status_code)

    return r.json()['access']['token']


def _need_refresh(token):
    """
    Return True if token should be refreshed.
    """

    # TODO check if token is valid by querying keystone

    str_exp_time = token['expires']
    token_time = time.strptime(str_exp_time, '%Y-%m-%dT%H:%M:%SZ')
    current_time = time.gmtime()

    return True if time.mktime(token_time) - time.mktime(current_time) < 60 * 5\
        else False


def get_auth_token(tenant, user, password, old_token):

    token = old_token

    if not old_token or _need_refresh(old_token):
        LOG.debug('Refreshing token...')
        token = _get_auth_token(tenant, user, password)

    return token


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
    role = 'pf9-ostackhost-vmw'
    headers = {'X-Auth-Token': token, 'Content-Type': 'application/json'}
    clusters = ""
    for resmgr_host in resmgr_hosts:
        url = '/'.join([resmgr_url, 'v1', 'hosts', resmgr_host, 'roles', role])
        resp = requests.get(url, verify=False, headers=headers)

        if resp.status_code not in (requests.codes.ok, 204):
            LOG.error('Resource manager query failed for host: %s with status: %d',
                                                    resmgr_host, resp.status_code)
        else:
            clusters = clusters + resp.json()['cluster_name']
    return clusters

def get_keystone_credentials(configfile):
    """
    Get the keystone credentials from the nova or glance service config.
    :param configfile: nova or glance config filename
    """
    cfg = ConfigParser()
    cfg.read(configfile)

    return cfg.get('keystone_authtoken', 'admin_user'), \
           cfg.get('keystone_authtoken', 'admin_password'), \
           cfg.get('keystone_authtoken', 'admin_tenant_name')


