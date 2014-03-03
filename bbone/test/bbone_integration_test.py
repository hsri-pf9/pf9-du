# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights Reserved.

"""
Integration test between backbone master and multiple slaves running
on simulated hosts.
"""

__author__ = 'leb'

import unittest
import ConfigParser
from bbcommon import vhost
from os import path, unlink
from os import environ as env
import subprocess
import sys
import requests
import time
import logging
import tempfile
import json
from bbcommon.utils import is_satisfied_by

test_data_0 = {
    'foo': {
        'version': '1.0',
        'url': 'http://zz.com/foo-1.0.rpm',
        'running': True,
        'config': {
            'default': {
                'x':1,
                'y':2
            },
            'backup': {
                'x':3,
                'y':5
            }
        }
    }
}

test_data_1 = {
    'ostackhost': {
        'version': '1.8',
        'url': 'http://www.foo.com/ostackhost-1.8.rpm',
        'running': True,
        'config': {
            'default': {
                'x':3,
                'y':2
            },
            'backup': {
                'x':3,
                'y':5
            }
        }
    }
}

class BBoneIntegrationTest(unittest.TestCase):

    def setUp(self):
        use_ssl = 'BBONE_TEST_USE_SSL' in env
        ssl_suffix = '_ssl' if use_ssl else ''
        master_conf_relpath = 'bbmaster/etc/bbmaster_test%s.conf' % ssl_suffix
        amqp_conf_relpath = 'bbslave/etc/pf9/amqp_test%s.conf' % ssl_suffix
        slave_conf_relpath = 'bbslave/etc/pf9/hostagent_test%s.conf' % ssl_suffix
        bbone_dir = path.realpath(path.join(path.dirname(__file__), '..'))
        master_conf = path.join(bbone_dir, master_conf_relpath)
        pecan_conf = path.join(bbone_dir, 'bbmaster/config.py')
        amqp_conf = path.join(bbone_dir, amqp_conf_relpath)
        slave_conf = path.join(bbone_dir, slave_conf_relpath)
        slave_script = path.join(bbone_dir, 'bbslave/bbslave/main.py')

        self.config = ConfigParser.ConfigParser()
        self.config.read([amqp_conf])
        amqp_host = self.config.get('amqp', 'host')
        self.amqp_endpoint = "http://%s:15672/api" % amqp_host
        self.config.set('amqp', 'virtual_host', vhost.generate_amqp_vhost())

        # Prepare a vhost, save to config, then write to temp file
        vhost.prep_amqp_broker(self.config, logging, self.amqp_endpoint)
        self.temp_amqp_conf = tempfile.NamedTemporaryFile(delete=False)
        self.config.write(self.temp_amqp_conf)
        self.temp_amqp_conf.close()

        self.slaves = []
        num_slaves = int(env.get('BBONE_TEST_NUM_SLAVES', '5'))
        env['AMQP_CONFIG_FILE'] = self.temp_amqp_conf.name
        env['HOSTAGENT_CONFIG_FILE'] = slave_conf
        env['BBMASTER_CONFIG_FILE'] = master_conf
        for i in range(num_slaves):
            env['HOSTAGENT_HOST_ID'] = self._host_id(i)
            self.slaves.append(subprocess.Popen([sys.executable,
                                                 slave_script], env=env))

        self.master = subprocess.Popen(['pecan', 'serve', pecan_conf], env=env)
        self.url = 'http://localhost:8082/v1/hosts/'
        self.wait_period = env.get('BBONE_TEST_WAIT_PERIOD', 1)
        self.wait_timeout = env.get('BBONE_TEST_WAIT_TIMEOUT', 30)

    def tearDown(self):
        self.master.terminate()
        self.master.wait(self.wait_timeout)
        if self.master.returncode is None:
            self.master.kill()
        for slave in self.slaves:
            slave.terminate()
            slave.wait(self.wait_timeout)
            if slave.returncode is None:
                slave.kill()
        vhost.clean_amqp_broker(self.config, logging, self.amqp_endpoint)
        unlink(self.temp_amqp_conf.name)

    def _wait_until(self, callback, *args):
        """
        Gets host descriptor list from REST API, passes it to the callback,
        and returns if the callback returns True. If the callback returns
        False, then sleeps and retries, up to a configured timeout.
        :param function callback: The callback function
        """
        elapsed = 0
        while elapsed < self.wait_timeout:
            try:
                r = requests.get(self.url)
                if r.status_code == 200:
                    # TODO: allow other return codes in the 20x range?
                    body = r.json()
                    if callback(body, *args):
                        return
                else:
                    print 'HTTP GET returned %d, retrying...' % r.status_code
            except requests.ConnectionError:
                print 'Connection refused, retrying ...'
            time.sleep(self.wait_period)
            elapsed += self.wait_period
        raise Exception('Timeout waiting for: %s' % repr(callback))

    def _host_id(self, i):
        """
        Generates a host ID for the slave with index i
        :param int i: the slave index
        :rtype: str
        """
        return 'host-%d' % i

    def _host_apps_url(self, i):
        return '%s%s/apps' % (self.url, self._host_id(i))

    def _check_http_status(self, r):
        assert r.status_code == 200

    def _verify_num_slaves(self, body):
        assert type(body) is list
        return len(body) == len(self.slaves)

    def _deploy_to_subset(self, modulus, test_data):
        for i in range(len(self.slaves)):
            if i % 2 == modulus:
                url = self._host_apps_url(i)
                r = requests.put(url, json.dumps(test_data))
                self._check_http_status(r)

    def _verify_subset(self, body, modulus, test_data):
        for host in body:
            host_id = host['host_id']
            i = int(host_id.split('-')[-1])
            if i % 2 == modulus:
                if not is_satisfied_by(test_data, host['apps']):
                    return False
        return True

    def test_integration(self):
        # Ensure master has detected the correct number of nodes
        self._wait_until(self._verify_num_slaves)

        # Deploy test_data_0 to even nodes, and verify
        self._deploy_to_subset(0, test_data_0)
        self._wait_until(self._verify_subset, 0, test_data_0)

        # Deploy test_data_1 to odd nodes, and verify
        self._deploy_to_subset(1, test_data_1)
        self._wait_until(self._verify_subset, 1, test_data_1)

        # Uninstall everything
        self._deploy_to_subset(0, {})
        self._wait_until(self._verify_subset, 0, {})
        self._deploy_to_subset(1, {})
        self._wait_until(self._verify_subset, 1, {})

