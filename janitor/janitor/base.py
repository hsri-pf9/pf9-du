#
# Copyright (c) 2014 Platform9 Systems.
# All rights reserved
#

__author__ = 'Platform9'

import logging
import requests
from janitor import utils
import json

LOG = logging.getLogger('janitor-daemon')


class Base(object):
    def __init__(self, conf):
        self._req_timeout = conf.get('DEFAULT', 'requestTimeout')
        self._wait = conf.get('DEFAULT', 'requestWaitPeriod')


class NovaBase(Base):
    def __init__(self, conf):
        super(NovaBase, self).__init__(conf)
        nova_config = conf.get('nova', 'configfile')
        self._auth_user, self._auth_pass, self._auth_tenant = \
                utils.get_keystone_credentials(nova_config)
        self._nova_url = conf.get('nova', 'endpointURI')

    def _nova_request(self, namespace, token, proj_id, req_type='get', json_body={}):
        url = '/'.join([self._nova_url, 'v2', proj_id, namespace])

        headers = {'X-Auth-Token': token, 'Content-Type': 'application/json'}

        assert(req_type in ('get', 'delete', 'post'))

        resp = None

        req_type = req_type.lower()

        if req_type == 'get':
            resp = requests.get(url, verify=False, headers=headers)
        elif req_type == 'delete':
            resp = requests.delete(url, verify=False, headers=headers)
        elif req_type == 'post':
            resp = requests.post(url, data=json.dumps(json_body), verify=False, headers=headers)

        if not resp:
            LOG.error("No response")
        elif resp.status_code not in (requests.codes.ok, 204, 202):
            LOG.error('Nova query failed: (%d) %s', resp.status_code, resp.text)

        return resp
