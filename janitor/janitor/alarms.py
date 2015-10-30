#
# Copyright (c) 2015, Platform9 Systems. All Rights Reserved
#

from ConfigParser import ConfigParser
import json
import logging
from os import path
import requests
import yaml


from utils import get_auth_token
from base import NovaBase

__author__ = 'Platform9'


LOG = logging.getLogger('janitor-daemon')

class AlarmsManager(NovaBase):
    def __init__(self, conf):
        super(AlarmsManager, self).__init__(conf)
        self._evaluation_periods = conf.get('ceilometer', 'eval_periods') or 6
        self._endpoint = conf.get('ceilometer', 'apiEndpoint')
        # TODO Look into alarm ownership and visibility
        ceilometer_config = conf.get('ceilometer',
                                     'configfile')

        cfg = ConfigParser()
        cfg.read(ceilometer_config)

        self._ceil_auth_url = cfg.get('service_credentials', 'os_auth_url')
        self._ceil_user = cfg.get('service_credentials', 'os_username')
        self._ceil_pass = cfg.get('service_credentials', 'os_password')
        self._ceil_tenant = cfg.get('service_credentials', 'os_tenant_name')

        # TODO: Make this configurable
        pipeline_file = 'pipeline.yaml'
        self._default_interval = self._parse_pipeline(pipeline_file)
        self._pipeline_cfg = self._parse_pipeline(pipeline_file)
        self._ceil_token = get_auth_token(self._ceil_tenant, self._ceil_user, self._ceil_pass, None)
        self._nova_token = get_auth_token(self._auth_tenant, self._auth_user, self._auth_pass, None)

    def _parse_pipeline(self, pipeline_file):

        default_interval = 600

        with open(path.join('/etc', 'ceilometer', pipeline_file)) as pf:
            data = yaml.load(pf)
            if 'sources' in data:
                srcs = data['sources']
                for src in srcs:
                    if 'meters' in src and any([s.startswith('pf9.services') for s in src['meters']]):
                        try:
                            default_interval = int(src['interval'])
                        except TypeError as te:
                            LOG.error('Error parsing pipeline: %s', te)
                            raise
        return default_interval

    def _request(self, namespace, token, proj_id, req_type='get', json_body={}):
        """
        Ceilometerclient implementation is buggy. It
        (1) Confuses insecure param
        (2) Cannot work with auth_token instead of username/password.
        :param namespace:
        :param token:
        :param proj_id:
        :param req_type:
        :param json_body:
        :return:
        """
        # url = '/'.join([self._endpoint, proj_id, namespace])
        url = '/'.join([self._endpoint, namespace])

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
        elif resp.status_code not in (requests.codes.ok, 204, 202, 201):
            LOG.error('Ceilometer query failed: (%d) %s', resp.status_code, resp.text)

        return resp

    def _get_missing_alarms_and_hosts(self):
        """
        Get
        (1) Hosts for which alarms are missing
        (2) Alarms for which hosts are missing
        """

        self._nova_token = get_auth_token(self._auth_tenant, self._auth_user,
                                          self._auth_pass, self._nova_token)


        resp = self._nova_request('os-hypervisors/detail', self._nova_token['id'],
                                  self._nova_token['tenant']['id'])

        if resp.status_code != requests.codes.ok:
            LOG.error('Unexpected error %(code)s querying nova hypervisors', dict(code=resp.status_code))
            return set(), set()

        nova_host_list = set([s['OS-EXT-PF9-HYP-ATTR:host_id'] for s in resp.json()['hypervisors']])

        self._ceil_token = get_auth_token(self._ceil_tenant, self._ceil_user,
                                          self._ceil_pass, self._ceil_token)
        resp = self._request('alarms', self._ceil_token['id'],
                             self._ceil_token['tenant']['id'])
        if resp.status_code != requests.codes.ok:
            LOG.error('Unexpected response %(code)s when querying alarms',
                      dict(code=resp.status_code))
            return set(), set()

        alarms = filter(lambda a: a['threshold_rule']['meter_name'] == "pf9.services.nodes.compute.status",
                        resp.json())
        alarm_hosts = set([a['name'] for a in alarms])

        missing_alarm_hosts = nova_host_list.difference(alarm_hosts)
        extra_alarm_hosts = alarm_hosts.difference(nova_host_list)

        return missing_alarm_hosts, \
               filter(lambda x: x['name'] in extra_alarm_hosts, alarms)


    def _add_alarms(self, missing_alarms):
        for h in missing_alarms:
            LOG.info('Adding alarm for node: %s', h)
            threshold_rule={"meter_name": "pf9.services.nodes.compute.status",
                            "evaluation_periods": self._evaluation_periods,
                            "period": self._default_interval,
                            "statistic": "sum",
                            "threshold": 1.0,
                            "query": [{"field": "resource_id", "type": "", "value": h, "op": "eq"}],
                            "comparison_operator": "lt",
                            }

            data = dict(type='threshold',
                        severity='critical',
                        name=h,
                        period=self._default_interval,
                        threshold_rule=threshold_rule,
                        description='Alarm when compute service is down for over an hour')
            resp = self._request('alarms', self._ceil_token['id'], self._ceil_token['tenant']['id'],
                                 req_type='post', json_body=data)
            if resp.status_code not in [requests.codes.ok, 201, 204]:
                LOG.error('Unexpected response %(code)s when creating alarm',
                          dict(code=resp.status_code))
                return

    def _delete_alarms(self, extra_alarms):
        for h in extra_alarms:
            LOG.info('Removing alarm for node: %s', h['name'])
            resp = self._request('alarms/%s' % h['alarm_id'], self._ceil_token['id'],
                                 self._ceil_token['tenant']['id'],
                                 req_type='delete')
            if resp.status_code not in [requests.codes.ok, 204]:
                LOG.error('Unexpected response %(code)s when deleting deleting alarm',
                          dict(code=resp.status_code))
                return

    def manage(self):
        """
        Maintain the alarms.
        (1) Create alarms for new hypervisors
        (2) Remove alarms for deleted hypervisors
        TODO: Change alarm monitoring based on changes to change in meter polling period
        """
        missing_alarms, extra_alarms = self._get_missing_alarms_and_hosts()

        self._add_alarms(missing_alarms)
        self._delete_alarms(extra_alarms)

