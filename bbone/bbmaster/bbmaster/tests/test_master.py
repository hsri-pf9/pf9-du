from bbmaster.tests import FunctionalTest

from six.moves.configparser import ConfigParser
import copy
import json
import logging as log
import os
import pika
import re
import tempfile
import time
import threading
import uuid

from pecan.testing import load_test_app
from pecan import set_config
from bbmaster.pf9_firmware_apps import get_fw_apps_cfg, insert_fw_apps_config
from bbcommon import constants
from bbcommon import vhost
from bbcommon.amqp import io_loop
from os.path import join, realpath, dirname

host_id = ':'.join(re.findall('..', '%012x' % uuid.getnode()))
bbmaster_dir = realpath(join(dirname(__file__), '../..'))
bbmaster_conf = join(bbmaster_dir, 'etc/bbmaster_test.conf')
config = ConfigParser()
config.read(bbmaster_conf)
config.set('amqp', 'virtual_host', vhost.generate_amqp_vhost())
log.basicConfig(level=getattr(log, 'INFO'))
amqp_host = config.get('amqp', 'host')
amqp_endpoint = "http://%s:15672/api" % amqp_host

global_conf = join(bbmaster_dir, 'etc/global_test.conf')
global_config = ConfigParser()
global_config.read(global_conf)
global_config.read(global_conf)
global_config.set('DEFAULT', 'DU_FQDN', 'test.platform9.com')

bad_opcode_msg = {
    'opcode': 'bogus'
}

initial_status = {
    'opcode': 'status',
    'data': {
        'host_id': host_id,
        'status': 'ok',
        'info': {},
        'apps': {
            "app_bar": {
                "version": "1.3",
                "running": True,
                "url": "http://www.foo.com/app_foo-1.8.rpm",
                "config": {
                    "default": {
                        "y":3,
                        "f":2
                    },
                    "backup": {
                        "w":3,
                        "z":5
                    }
                }
            },
            "app_foo": {
                "version": "1.8",
                "running": False,
                "url": "http://www.foo.com/app_foo-1.8.rpm",
                "config": {
                    "default": {
                        "x":3,
                        "y":2
                    },
                    "backup": {
                        "x":3,
                        "y":5
                    }
                }
            }
        },
        'host_agent': {
            'version': '9.1.1',
            'status': 'running'
        }
    }
}

bad_initial_status = {
    'opcode': 'status',
    'data': {
        'status': 'ok',
        'info': {},
        'apps': {},
        'host_agent': {}
    }
}

test_data = {
    "app_bar": {
        "version": "1.3",
        "running": False,
        "url": "http://www.foo.com/app_foo-1.8.rpm",
        "rank": "1.6",
        "config": {
            "default": {
                "y":3,
                "f":2
                },
            "backup": {
                "w":3,
                "z":5
                }
            }
        }
    }


def setup_module():
    vhost.prep_amqp_broker(config, log, amqp_endpoint)

def teardown_module():
    vhost.clean_amqp_broker(config, log, amqp_endpoint)

def _setup_slave(init_msg, host_topic):
    """
    Starts out slave to work with the master as part of the tests. Uses the
    initial status param as the data it advertises to the master on startup.
    """
    username = config.get('amqp', 'username')
    password = config.get('amqp', 'password')
    credentials = pika.PlainCredentials(username=username, password=password)
    state = {}

    def send_msg(msg):
        log.info("[%s] Mock slave sending message: %s",
                    threading.currentThread().getName(), msg)
        channel = state['channel']
        log.info('state: %s', state)
        channel.basic_publish(exchange=constants.BBONE_EXCHANGE,
                              routing_key=constants.MASTER_TOPIC,
                              body=json.dumps(msg))

    def before_consuming():
        # Verify bbmaster can survive a message with bogus opcode (IAAS-1665)
        send_msg(bad_opcode_msg)
        # Send the real initial message
        send_msg(init_msg)


    def mock_consume_msg(ch, method, properties, body):
        log.info('[%s] Mock slave received message %s',
                threading.currentThread().getName(), body)
        out_msg = copy.deepcopy(init_msg)
        in_msg = json.loads(body.decode())
        if in_msg['opcode'] == 'ping':
            # Return init_msg
            pass
        else:
            out_msg['data']['apps'] = in_msg['data']
        send_msg(out_msg)


    recv_keys = [constants.BROADCAST_TOPIC, host_topic]

    log.info("Starting IO loop slave...")
    io_loop(log=log,
            queue_name='',
            host=config.get('amqp', 'host'),
            credentials=credentials,
            exch_name=constants.BBONE_EXCHANGE,
            recv_keys=recv_keys,
            state=state,
            before_processing_msgs_cb=before_consuming,
            consume_cb=mock_consume_msg,
            virtual_host=config.get('amqp', 'virtual_host'))


def validate_with_retry(validator, retries, sleep_interval, *validator_args):
    """
    Validates the provided validator method, retrying it the specified
    number of times. Returns True if the validator succeeds within the number of
    retries specified.
    """
    tries = 1
    while tries < retries:
        if not validator(*validator_args):
            time.sleep(sleep_interval)
            tries += 1
        else:
            break

    return tries < retries

def validate_host_present(provider, host_id):
    body = provider.get_host_ids()
    return host_id in body

class TestBbMaster(FunctionalTest):
    """
    Test backbone master
    """

    def setUp(self):
        self.temp_conf = tempfile.NamedTemporaryFile(delete=False, mode='w')
        config.write(self.temp_conf)
        self.temp_conf.close()
        os.environ['BBMASTER_CONFIG_FILE'] = self.temp_conf.name

        self.global_conf = tempfile.NamedTemporaryFile(delete=False, mode='w')
        global_config.write(self.global_conf)
        self.global_conf.close()
        os.environ['GLOBAL_CONFIG_FILE'] = self.global_conf.name

        self.app = load_test_app(os.path.join(
            os.path.dirname(__file__),
            'master_config.py'
        ))


    def tearDown(self):
        os.unlink(self.temp_conf.name)
        set_config({}, overwrite=True)


    def test_master(self):
        log.info('Starting test %s:%s', self.__class__, __name__)
        # We want the provider to come up only after the setUp step above has
        # built the config file. So, import it here.
        from bbmaster.bbone_provider_pf9_pika import provider

        thread_id = 'test_master'
        test_host_id = '%s-%s' % (host_id, thread_id)
        init_msg = copy.deepcopy(initial_status)
        init_msg['data']['host_id'] = test_host_id
        t = threading.Thread(name=thread_id, target=_setup_slave,
                args=(init_msg, test_host_id))
        t.daemon = True
        t.start()

        # TEST SUMMARY
        # Ensure the slave registered with the master and published its status
        validation_result = validate_with_retry(validate_host_present, 20, 3,
                                                provider, test_host_id)
        assert validation_result

        host_info = provider.get_hosts([test_host_id])
        log.info('Discovered host info: %s', host_info)
        assert host_info[0]['apps'] == init_msg['data']['apps']

        # TEST SUMMARY
        # Set the configuration for a host. Ensure the desired apps for the
        # master are updated and then even the slave reports updated status

        firmware_apps_cfg = get_fw_apps_cfg()
        provider.set_host_apps(test_host_id, copy.deepcopy(test_data))
        # Check that the master has registered the desired configuration first,
        # and then check that the actual configuration converged with it.
        test_data_with_fw_apps = insert_fw_apps_config(copy.deepcopy(test_data),
                                                     firmware_apps_cfg,
                                                     host_state=host_info[0])
        assert test_data_with_fw_apps == provider.desired_apps[test_host_id]

        def validate_host_apps(host_id, expected_host_data):
            host_info = provider.get_hosts([host_id])
            expected_with_fw_apps = insert_fw_apps_config(
                copy.deepcopy(expected_host_data), firmware_apps_cfg,
                host_state=host_info[0])
            cur_data = provider.get_hosts([host_id])
            cur_data_with_fw_apps = provider.get_hosts([host_id],
                                                     show_firmware_apps=True)
            return expected_host_data == cur_data[0]['apps'] and \
                cur_data_with_fw_apps[0]['apps'] == expected_with_fw_apps

        assert validate_with_retry(validate_host_apps, 20, 3, test_host_id, test_data)

        # TEST SUMMARY
        # Set the same configuration as that currently on the host. Ensure that
        # the desired apps state remains same as before.
        cur_data = provider.get_hosts([test_host_id])
        previous_state = cur_data[0]['apps']

        provider.set_host_apps(test_host_id, test_data)
        log.info('Desired apps state: %s ' % provider.desired_apps)
        assert insert_fw_apps_config(previous_state, firmware_apps_cfg, host_state=cur_data[0]) == provider.desired_apps[test_host_id]

    def test_remove_apps_from_missing_host(self):
        from bbmaster.bbone_provider_pf9_pika import provider
        host_id = 'idontexist'
        provider.set_host_apps(host_id, {})
        host_info = provider.get_hosts([host_id])
        self.assertEquals(1, len(host_info))
        self.assertEquals('missing', host_info[0]['status'])

        # these are required in resmgr for its 'responding' calculations
        self.assertTrue(host_info[0]['timestamp'])
        self.assertTrue(host_info[0]['timestamp_on_du'])

class TestBBMasterBadStatus (FunctionalTest):

    def setUp(self):
        self.temp_conf = tempfile.NamedTemporaryFile(delete=False, mode='w')
        config.write(self.temp_conf)
        self.temp_conf.close()
        os.environ['BBMASTER_CONFIG_FILE'] = self.temp_conf.name

        self.global_conf = tempfile.NamedTemporaryFile(delete=False, mode='w')
        global_config.write(self.global_conf)
        self.global_conf.close()
        os.environ['GLOBAL_CONFIG_FILE'] = self.global_conf.name

        self.app = load_test_app(os.path.join(
            os.path.dirname(__file__),
            'master_config.py'
        ))

    def tearDown(self):
        os.unlink(self.temp_conf.name)
        set_config({}, overwrite=True)

    def test_master_bad_status(self):
        log.info('Starting test %s:%s', self.__class__, __name__)
        # We want the provider to come up only after the setUp step above has
        # built the config file. So, import it here.
        from bbmaster.bbone_provider_pf9_pika import provider
        t = threading.Thread(name='test_master_bad_status', target=_setup_slave,
                args=(bad_initial_status, host_id))
        t.daemon = True
        t.start()

        # TEST SUMMARY
        # Ensure the slave has sent a bad status which the master has rejected.
        # Also check the there is no data associated with that host
        validate_res = validate_with_retry(validate_host_present, 5, 3,
                                           provider, host_id)
        assert not validate_res

        host_info = provider.get_hosts([host_id])
        assert not host_info


class TestBBMasterBadSetOp(FunctionalTest):

    def setUp(self):
        self.temp_conf = tempfile.NamedTemporaryFile(delete=False, mode='w')
        config.write(self.temp_conf)
        self.temp_conf.close()
        os.environ['BBMASTER_CONFIG_FILE'] = self.temp_conf.name

        self.global_conf = tempfile.NamedTemporaryFile(delete=False, mode='w')
        global_config.write(self.global_conf)
        self.global_conf.close()
        os.environ['GLOBAL_CONFIG_FILE'] = self.global_conf.name

        self.app = load_test_app(os.path.join(
            os.path.dirname(__file__),
            'master_config.py'
        ))

    def tearDown(self):
        os.unlink(self.temp_conf.name)
        set_config({}, overwrite=True)

    def test_master_bad_set_op(self):
        log.info('Starting test %s:%s', self.__class__, __name__)
        # We want the provider to come up only after the setUp step above has
        # built the config file. So, import it here.
        from bbmaster.bbone_provider_pf9_pika import provider
        thread_id = 'test_master_bad_set_op'
        test_host_id = '%s-%s' % (host_id, thread_id)
        init_msg = copy.deepcopy(initial_status)
        init_msg['data']['host_id'] = test_host_id
        t = threading.Thread(name='test_master_bad_set_op', target=_setup_slave,
                args=(init_msg, test_host_id))
        t.daemon = True
        t.start()

        # TEST SUMMARY
        # Ensure the slave registered with the master and published its status
        assert validate_with_retry(validate_host_present, 20, 3,
                                   provider, test_host_id)

        host_info = provider.get_hosts([test_host_id])
        log.info('Discovered host info: %s', host_info)
        assert host_info[0]['apps'] == init_msg['data']['apps']
        prev_apps = host_info[0]['apps']

        # TEST SUMMARY
        # Set an invalid configuration for a host. Ensure that the master
        # doesn't honor this configuration.
        provider.set_host_apps(test_host_id, [])
        log.info('Desired apps in master: %s ' % provider.desired_apps)
        assert provider.desired_apps[test_host_id] == None

        host_apps = provider.get_hosts([test_host_id])[0]['apps']
        assert prev_apps == host_apps


