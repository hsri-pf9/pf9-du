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


def get_host_app_info(host_id):
    url = "http://localhost:8082/v1/hosts/%s/apps" % host_id
    headers = {'Content-Type': 'application/json'}

    resp = requests.get(url, verify=False, headers=headers)

    if resp.status_code not in (requests.codes.ok, 204):
        LOG.error('BBmaster query failed: %d', resp.status_code)
        return None
    return resp.json()
