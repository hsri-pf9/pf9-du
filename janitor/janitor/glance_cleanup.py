#
# Copyright (c) Platform9 Systems. All rights reserved
#

__author__ = 'Platform9'

import requests
import logging
from janitor import utils

LOG = logging.getLogger('janitor-daemon')


class GlanceCleanup(object):

    def __init__(self, conf):
        self._resmgr_url = conf.get('resmgr', 'endpointURI')
        self._glance_api_url = conf.get('glance', 'apiEndpoint')
        self._glance_imagelibs_url = conf.get('glance', 'imglibsEndpoint')
        glance_config = conf.get('nova', 'configfile')
        self._auth_user, self._auth_pass, self._auth_tenant = \
                utils.get_keystone_credentials(glance_config)

    def _get_imagelibs(self, token):
        url = '%s/imagelibs' % self._glance_imagelibs_url
        resp = requests.get(url, headers={'x-auth-token': token}, verify=False)
        if resp.status_code != 200:
            msg = 'failed to get glance imagelibrary list, code = %d' % \
                    resp.status_code
            LOG.error(msg)
            raise RuntimeError(msg)
        return resp.json()

    def _get_images(self, token):
        url = '%s/images/detail' % self._glance_api_url
        resp = requests.get(url, headers={'x-auth-token': token}, verify=False)
        if resp.status_code != 200:
            msg = 'failed to get glance images list, code = %d' % \
                    resp.status_code
            LOG.error(msg)
            raise RuntimeError(msg)
        return resp.json()['images']

    def _delete_imagelib(self, token, imagelib_id):
        url = '%s/imagelibs/%s' % (self._glance_imagelibs_url, imagelib_id)
        resp = requests.delete(url, headers={'x-auth-token': token}, verify=False)
        if resp.status_code != 200:
            msg = 'failed to remove imagelibrary %s, code = %d' % \
                    (imagelib_id, resp.status_code)
            LOG.error(msg)

    def _delete_image(self, token, image_id):
        url = '%s/images/%s' % (self._glance_api_url, image_id)
        resp = requests.delete(url, headers={'x-auth-token': token}, verify=False)
        if resp.status_code != 200:
            msg = 'failed to remove image %s, code = %d' % \
                    (image_id, resp.status_code)
            LOG.error(msg)

    def cleanup(self):
        """
        Remove images and imagelibrary entries from glance registry hosts that
        no longer show up in resmgr.
        """
        token, _ = utils.get_auth_token(self._auth_tenant, self._auth_user,
                self._auth_pass)

        resp = utils.get_resmgr_hosts(self._resmgr_url, token)

        if resp.status_code != 200:
            LOG.error('failed to get list of hosts from resmgr, code = %d',
                      resp.status_code)
            return

        resmgr_data = resp.json()
        resmgr_ids = set(h['id']
                for h in filter(lambda h: h['state'] == 'active', resmgr_data))

        images = self._get_images(token)
        for image in images:
            if image['properties']['pf9_imagelib_id'] not in resmgr_ids:
                LOG.info('host %s has been removed, removing image %s',
                        image['properties']['pf9_imagelib_id'], image['name'])
                self._delete_image(token, image['id'])

        # note imagelibs api will return all, including deleted entries
        imagelibs = self._get_imagelibs(token)
        for imagelib in imagelibs:
            if imagelib['host_id'] not in resmgr_ids and \
               not imagelib['deleted']:
                LOG.info('removing image library entry for host %s',
                        imagelib['host_id'])
                self._delete_imagelib(token, imagelib['host_id'])

