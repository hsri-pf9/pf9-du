# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

"""
Tests a backbone slave agent by simulating a master server.
To use, configure an AMQP broker using the config object.
The slave is run in a thread.
"""

__author__ = 'leb'

import json
from nose import with_setup
from bbcommon import constants
from bbcommon.amqp import io_loop
from bbcommon.utils import is_satisfied_by
from bbcommon import vhost
from six.moves.configparser import ConfigParser
import pika
import logging as log
import threading
from bbslave.slave import reconnect_loop
import test_slave_data
import os
import shutil

amqp_host = "rabbitmq-rspc-01.platform9.horse"
amqp_endpoint = "http://%s:15672/api" % amqp_host

config = ConfigParser()
config.add_section('amqp')
config.add_section('amqp_host')
config.set('amqp_host', 'host', amqp_host)
config.set('amqp', 'username', 'guest')
config.set('amqp', 'password', 'm1llenn1umFalc0n')
config.set('amqp', 'virtual_host', vhost.generate_amqp_vhost())
config.add_section('hostagent')
config.set('hostagent', 'connection_retry_period', '5')
config.add_section('download')
config.set('download', 'protocol', 'http')
config.set('download', 'port', '9080')

# The heartbeat period has to be long enough for the slave to generate
# a 'failed' message for the failure case after all other tests, but
# short enough to make the overall unit test complete in a reasonable
# amount of time. Also, max_converge_attempts must be 2 for this test.
# FIXME: the test is timing and system load sensitive. Find a better way if flaky!
config.set('hostagent', 'heartbeat_period', '15')
config.set('hostagent', 'max_converge_attempts', '2')

config.set('hostagent', 'log_level_name', 'INFO')
config.set('hostagent', 'app_cache_dir', '/tmp/appcache')
config.set('hostagent', 'USE_MOCK', '1')
config.set('hostagent', 'console_logging', '1')
config.set('hostagent', 'allow_exit_opcode', 'true')
CACHED_DESIRED_CONFIG_BASEDIR='/tmp/hostagent_test'
config.set('hostagent', 'desired_config_basedir_path', CACHED_DESIRED_CONFIG_BASEDIR)
if os.path.exists(CACHED_DESIRED_CONFIG_BASEDIR):
    shutil.rmtree(CACHED_DESIRED_CONFIG_BASEDIR)
log.basicConfig(level=getattr(log, 'INFO'))

# These have to be global. Python 2.x makes it hard for nested functions
# to modify outer variables that are not globals.
cur_desired_state = None
expecting_converging_state = False
retry_countdown = 0

def _exercise_testroutine(test_data):
    """
    Core test driver
    """
    username = config.get('amqp', 'username')
    password = config.get('amqp', 'password')
    credentials = pika.PlainCredentials(username=username, password=password)
    state = {}

    def before_consuming():
        # Start the slave daemon.
        # It sends a status message upon startup.
        t = threading.Thread(target=reconnect_loop, args=(config,))
        t.daemon = True
        t.start()
        state['slave_thread'] = t
        return

    def consume_msg(ch, method, properties, body):
        def finish_consuming(method_frame):
            global cur_desired_state, expecting_converging_state, retry_countdown
            log.info('Received: %s', body)

            # If the support message is received
            if body['opcode'] == 'support':
                return

            assert body['opcode'] == 'status'

            if expecting_converging_state:
                assert body['data']['status'] == 'converging'
                expecting_converging_state = False
                assert ('desired_apps' in body['data'] and
                        cur_desired_state is not None and
                        is_satisfied_by(cur_desired_state, body['data']['desired_apps']))
                return

            if retry_countdown:
                assert ('desired_apps' in body['data'] and
                        cur_desired_state is not None and
                        is_satisfied_by(cur_desired_state, body['data']['desired_apps']))
                retry_countdown -= 1
                if retry_countdown:
                    assert body['data']['status'] == 'retrying'
                    expecting_converging_state = True
                    return
                assert body['data']['status'] == 'failed'
            else:
                assert body['data']['status'] == 'ok'
                assert 'desired_apps' not in body['data']
                if cur_desired_state is not None:
                    assert is_satisfied_by(cur_desired_state, body['data']['apps'])

            if not len(test_data):
                log.info('Done.')
                channel = state['channel']
                msg = {'opcode': 'exit'}
                channel.basic_publish(exchange=constants.BBONE_EXCHANGE,
                                      routing_key=body['data']['host_id'],
                                      body=json.dumps(msg))
                channel.close()
                conn = state['connection']
                conn.close()
                state['slave_thread'].join()
                return

            cur_test = test_data.pop(0)
            expecting_converging_state = cur_test['expect_converging']
            retry_countdown = cur_test.get('retry_countdown', 0)
            opcode = cur_test['opcode']
            cur_desired_state = cur_test['desired_config']

            msg = {'opcode': opcode, 'data': cur_desired_state}
            state['channel'].basic_publish(exchange=constants.BBONE_EXCHANGE,
                                  routing_key=body['data']['host_id'],
                                  body=json.dumps(msg))
        def declare_bbslave_q(host_id):
            """
            Declare a queue for the host. Also, bind it to the bbone exchange.
            These queues are deleted when the server restarts.
            """
            def on_bbslave_queue_declare(method_frame):
                routing_key = routing_keys.pop(0)
                callback = on_bbslave_queue_declare if len(routing_keys) else finish_consuming
                state['channel'].queue_bind(exchange=constants.BBONE_EXCHANGE,
                                            queue=queue_name,
                                            routing_key=routing_key,
                                            callback=callback)

            routing_keys = [constants.BROADCAST_TOPIC, host_id]
            queue_name = constants.HOSTAGENT_QUEUE_PREFIX + host_id
            state['channel'].queue_declare(queue=queue_name,
                                           callback=on_bbslave_queue_declare)

        body = json.loads(body)
        host_id = body['data']['host_id']
        # Finish consuming the message after setting up the bbslave queue
        declare_bbslave_q(host_id)

    io_loop(log=log,
            host=config.get('amqp_host', 'host'),
            queue_name='',
            credentials=credentials,
            exch_name=constants.BBONE_EXCHANGE,
            recv_keys=[constants.MASTER_TOPIC],
            state=state,
            before_processing_msgs_cb=before_consuming,
            consume_cb=consume_msg,
            virtual_host=config.get('amqp', 'virtual_host'))

def prep_amqp_broker():
    vhost.prep_amqp_broker(config, log, amqp_endpoint)

def clean_amqp_broker():
    vhost.clean_amqp_broker(config, log, amqp_endpoint)

@with_setup(prep_amqp_broker, clean_amqp_broker)
def test_slave_with_different_number_of_services():
    """
    Simulates a backbone master to test operations through a slave agent with different number of services
    """

    config.set('hostagent', 'mock_app_class', 'MockRemoteAppWithDifferentNumberOfServices')
    test_data = test_slave_data.test_data_different_number_of_services
    _exercise_testroutine(test_data)

@with_setup(prep_amqp_broker, clean_amqp_broker)
def test_slave_install():
    """
    Simulates a backbone master to test install operations through a slave agent
    """

    config.set('hostagent', 'mock_app_class', 'MockRemoteApp')
    test_data = test_slave_data.test_data_install
    _exercise_testroutine(test_data)


@with_setup(prep_amqp_broker, clean_amqp_broker)
def test_slave_ping():
    """
    Simulates a backbone master to test ping operations through a slave agent
    """

    config.set('hostagent', 'mock_app_class', 'MockRemoteApp')
    test_data = test_slave_data.test_data_ping
    _exercise_testroutine(test_data)

@with_setup(prep_amqp_broker, clean_amqp_broker)
def test_slave_config():
    """
Simulates a backbone master to test config operations through a slave agent
"""

    config.set('hostagent', 'mock_app_class', 'MockRemoteApp')
    test_data = test_slave_data.test_data_config
    _exercise_testroutine(test_data)

