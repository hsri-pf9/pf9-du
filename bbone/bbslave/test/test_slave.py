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
from ConfigParser import ConfigParser
import pika
import logging as log
import threading
from bbslave.slave import reconnect_loop
import test_slave_data

amqp_host = "rabbitmq.platform9.sys"
amqp_endpoint = "http://%s:15672/api" % amqp_host

config = ConfigParser()
config.add_section('amqp')
config.set('amqp', 'host', amqp_host)
config.set('amqp', 'username', 'guest')
config.set('amqp', 'password', 'nova')
config.set('amqp', 'virtual_host', vhost.generate_amqp_vhost())
config.add_section('hostagent')
config.set('hostagent', 'connection_retry_period', '5')
config.set('hostagent', 'heartbeat_period', '3600')
config.set('hostagent', 'log_level_name', 'INFO')
config.set('hostagent', 'app_cache_dir', '/tmp/appcache')
config.set('hostagent', 'USE_MOCK', '1')
log.basicConfig(level=getattr(log, 'INFO'))

# These have to be global. Python 2.x makes it hard for nested functions
# to modify outer variables that are not globals.
cur_desired_state = None
expecting_converging_state = False
expecting_errors = False

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
        return

    def consume_msg(ch, method, properties, body):
        global cur_desired_state, expecting_converging_state, expecting_errors
        log.info('Received: %s', body)
        body = json.loads(body)
        assert body['opcode'] == 'status'

        if expecting_converging_state:
            assert body['data']['status'] == 'converging'
            expecting_converging_state = False
            return

        expected_status = 'errors' if expecting_errors else 'ok'
        assert body['data']['status'] == expected_status

        if (cur_desired_state is not None) and (not expecting_errors):
            assert is_satisfied_by(cur_desired_state, body['data']['apps'])

        if not len(test_data):
            log.info('Done.')
            channel = state['channel']
            channel.close()
            conn = state['connection']
            conn.close()
            return

        cur_test = test_data.pop(0)
        expecting_converging_state = cur_test['expect_converging']
        expecting_errors = cur_test.get('expect_errors', False)
        opcode = cur_test['opcode']
        cur_desired_state = cur_test['desired_config']

        msg = {'opcode': opcode, 'data': cur_desired_state}
        state['channel'].basic_publish(exchange=constants.BBONE_EXCHANGE,
                              routing_key=body['data']['host_id'],
                              body=json.dumps(msg))

    io_loop(host=config.get('amqp', 'host'),
            credentials=credentials,
            exch_name=constants.BBONE_EXCHANGE,
            recv_keys=[constants.MASTER_TOPIC],
            state=state,
            before_consuming_cb=before_consuming,
            consume_cb=consume_msg,
            virtual_host=config.get('amqp', 'virtual_host'))

def prep_amqp_broker():
    vhost.prep_amqp_broker(config, log, amqp_endpoint)

def clean_amqp_broker():
    vhost.clean_amqp_broker(config, log, amqp_endpoint)

@with_setup(prep_amqp_broker, clean_amqp_broker)
def test_slave_install():
    """
    Simulates a backbone master to test install operations through a slave agent
    """

    test_data = test_slave_data.test_data_install
    _exercise_testroutine(test_data)


@with_setup(prep_amqp_broker, clean_amqp_broker)
def test_slave_ping():
    """
    Simulates a backbone master to test ping operations through a slave agent
    """

    test_data = test_slave_data.test_data_ping
    _exercise_testroutine(test_data)

@with_setup(prep_amqp_broker, clean_amqp_broker)
def test_slave_config():
    """
    Simulates a backbone master to test config operations through a slave agent
    """

    test_data = test_slave_data.test_data_config
    _exercise_testroutine(test_data)
