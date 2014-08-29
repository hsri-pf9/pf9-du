#
# Copyright (c) Platform9 Systems. All rights reserved
#

import json
import logging
import requests

from ConfigParser import ConfigParser

LOG = logging.getLogger(__name__)

def get_auth_token(tenant, user, password):
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

    r = requests.post(url, json.dumps(data),
            verify=False, headers={'Content-Type': 'application/json'})

    if r.status_code != requests.codes.ok:
        raise RuntimeError('Token request returned: %d' % r.status_code)

    return r.json()['access']['token']['id'],\
           r.json()['access']['token']['tenant']['id']

def get_resmgr_hosts(resmgr_url, token):
    url = '/'.join([resmgr_url, 'v1', 'hosts'])
    headers = {'X-Auth-Token': token, 'Content-Type': 'application/json'}

    resp = requests.get(url, verify=False, headers=headers)

    if resp.status_code not in (requests.codes.ok, 204):
        LOG.error('Resource manager query failed: %d', resp.status_code)

    return resp

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


