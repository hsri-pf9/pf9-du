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
from os import unlink
from os.path import join, realpath, dirname
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
        'rank': '3.3',
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
        'rank': '3.3',
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

class WaitTimeoutException(Exception):
    pass

class BBoneIntegrationTest(unittest.TestCase):

    def setUp(self):
        bbone_dir = realpath(join(dirname(__file__), '..'))
        master_conf = join(bbone_dir, 'bbmaster/etc/bbmaster_test.conf')
        pecan_conf = join(bbone_dir, 'bbmaster/test_config.py')
        slave_conf = join(bbone_dir, 'bbslave/etc/pf9/hostagent_test.conf')
        slave_script = join(bbone_dir, 'bbslave/bbslave/main.py')
        ca_certs = join(bbone_dir, 'etc/pf9/certs/testca/cacert.pem')
        slave_key = join(bbone_dir, 'etc/pf9/certs/hostagent/key.pem')
        slave_cert = join(bbone_dir, 'etc/pf9/certs/hostagent/cert.pem')
        master_key = join(bbone_dir, 'etc/pf9/certs/bbmaster/key.pem')
        master_cert = join(bbone_dir, 'etc/pf9/certs/bbmaster/cert.pem')

        self.config = ConfigParser.ConfigParser()
        self.config.read([slave_conf, master_conf])
        amqp_host = self.config.get('amqp_host', 'host')
        self.amqp_endpoint = "http://%s:15672/api" % amqp_host
        self.config.set('amqp', 'virtual_host', vhost.generate_amqp_vhost())
        vhost.prep_amqp_broker(self.config, logging, self.amqp_endpoint)

        use_ssl = 'BBONE_TEST_USE_SSL' in env
        if use_ssl:
            self.config.add_section('ssl')
            self.config.set('ssl', 'ca_certs', ca_certs)
            self.config.set('ssl', 'certfile', slave_cert)
            self.config.set('ssl', 'keyfile', slave_key)
        self.tmp_slave_conf = tempfile.NamedTemporaryFile(delete=False)
        self.config.write(self.tmp_slave_conf)
        self.tmp_slave_conf.close()

        if use_ssl:
            self.config.set('ssl', 'certfile', master_cert)
            self.config.set('ssl', 'keyfile', master_key)
        self.tmp_master_conf = tempfile.NamedTemporaryFile(delete=False)
        self.config.write(self.tmp_master_conf)
        self.tmp_master_conf.close()

        self.slaves = []
        num_slaves = int(env.get('BBONE_TEST_NUM_SLAVES', '5'))
        env['HOSTAGENT_CONFIG_FILE'] = self.tmp_slave_conf.name
        env['BBMASTER_CONFIG_FILE'] = self.tmp_master_conf.name
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
        try:
            self._wait_until_generic(self.master.poll, 1, None)
        except WaitTimeoutException as ex:
            self.master.kill()
        for slave in self.slaves:
            slave.terminate()
            try:
                self._wait_until_generic(slave.poll, 1, None)
            except WaitTimeoutException as ex:
                slave.kill()
        vhost.clean_amqp_broker(self.config, logging, self.amqp_endpoint)
        unlink(self.tmp_slave_conf.name)
        unlink(self.tmp_master_conf.name)

    def _wait_until_generic(self, callback, delta, check_callback,
                            *largs, **kwargs):
        """
        Waits for an acceptable return of callback(*args, **kwargs).

        :type callback: callable
        :param callback: function to call and examine response for
        :type delta: int
        :param delta: time between callback return checks
        :type check_callback: callable
        :param check_callback: function that returns True
                               if the return value of callback(*args)
                               is acceptable. The default is a value
                               that is anything other than None.
        """
        curtime = time.time()
        maxtime = curtime + self.wait_timeout
        while curtime < maxtime:
            ret = callback(*largs, **kwargs)
            if check_callback:
                if check_callback(ret) == True:
                    return ret
            elif ret != None:
                return ret
            time.sleep(delta)
            curtime = time.time()
        ex = WaitTimeoutException()
        ex.callback = callback
        ex.largs = largs
        ex.kwargs = kwargs.copy()
        raise ex

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

