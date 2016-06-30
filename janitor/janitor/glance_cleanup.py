#
# Copyright (c) Platform9 Systems. All rights reserved
#

import json
import logging
import re
import requests
from janitor import utils

LOG = logging.getLogger('janitor-daemon')

STATUS_RE = re.compile(r'pf9status\.(\S*)')
STATUS_OFFLINE = 'offline'

class GlanceCleanup(object):

    def __init__(self, conf):
        self._resmgr_url = conf.get('resmgr', 'endpointURI')
        self._glance_url = conf.get('glance', 'apiEndpoint')
        self._auth = None
        glance_config = conf.get('nova', 'configfile')
        self._auth_user, self._auth_pass, self._auth_tenant = \
                utils.get_keystone_credentials(glance_config)

    def _get_images(self, token):
        url = '%s/v2/images?limit=100' % self._glance_url
        images = []
        while True:
            resp = requests.get(url,
                                headers={'x-auth-token': token},
                                verify=False)
            resp.raise_for_status()
            body = resp.json()
            chunk = body['images']
            images += chunk
            next_url = body.get('next', None)
            if next_url:
                url = self._glance_url + next_url
            else:
                LOG.info('Retrieved %d images from glance', len(images))
                return images

    def _change_properties(self, token, imageid, patch_spec):
        """
        Add or update a set of image properties on an images.
        :param token: keystone token
        :param imageid: the imageid
        :param patch_spec: list of dictionaries like in:
        http://specs.openstack.org/openstack/glance-specs/specs/api/v2/http-patch-image-api-v2.html
        """
        if not patch_spec:
            return
        headers={'Content-Type': 'application/openstack-images-v2.1-json-patch',
                 'X-Auth-Token': token}
        url = '%s/v2/images/%s' % (self._glance_url, imageid)
        resp = requests.patch(url,
                              headers=headers,
                              data=json.dumps(patch_spec))
        resp.raise_for_status()

    @staticmethod
    def _host_has_glance(host):
        """
        True if host has a glance role.
        """
        return bool(set(['pf9-glance-role', 'pf9-glance-role-vmw']) &
                    set(host.get('roles', [])))

    @staticmethod
    def _get_host_status_update(prop_name, curr_value, host):
        """
        Based on the status of the host, remove or update the pf9status
        variable for the host's id.
        """
        updates = []
        if not GlanceCleanup._host_has_glance(host):
            LOG.info('host %s is not authorized for glance, removing status')
            updates.append({'op': 'remove', 'name': '/%s' % prop_name})
        elif curr_value != STATUS_OFFLINE:
            host_state = host.get('state', None)
            role_status = host.get('role_status', None)
            if host_state != 'active' or role_status != 'ok':
                LOG.warn('host %s has host state = %s and role_status = %s, '
                         'marking image offline', host['id'], host_state,
                         role_status)
                updates.append({'op': 'add',
                                'path': '/%s' % prop_name,
                                'value': STATUS_OFFLINE})
        return updates

    def cleanup(self):
        """
        update image properties based on the health of the host and role
        """
        self._auth = utils.get_auth_token(self._auth_tenant, self._auth_user,
                                          self._auth_pass, self._auth)
        token = self._auth['id']
        resp = utils.get_resmgr_hosts(self._resmgr_url, token)
        resp.raise_for_status()
        resp_list = resp.json()
        hosts = {h['id']: h for h in resp_list}
        images = self._get_images(token)
        updates = []
        for image in images:
            for name, val in image.iteritems():
                match = STATUS_RE.search(name)
                if match:
                    host_id = match.group(1)
                    if host_id in hosts.keys():
                        host = hosts[host_id]
                        updates += self._get_host_status_update(name, val, host)
                    else:
                        LOG.info('host %s is not authorized for glance, '
                                 'removing status', host_id)
                        updates.append({'op': 'remove', 'path': '/%s' % name})
            if updates:
                self._change_properties(token, image['id'], updates)
