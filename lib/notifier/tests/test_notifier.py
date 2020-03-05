# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights Reserved.

from unittest import TestCase
from six.moves.configparser import ConfigParser
import json
import logging
import pika, pika.channel, pika.connection
import threading
from bbcommon import vhost
from bbcommon.amqp import io_loop
import notifier
import time

config = ConfigParser()
config.add_section('amqp')
config.set('amqp', 'host', 'rabbitmq')
config.set('amqp', 'username', 'guest')
config.set('amqp', 'password', 'nova')
log = logging
log.basicConfig(level=logging.INFO)
config.set('amqp', 'virtual_host', vhost.generate_amqp_vhost())
log.basicConfig(level=getattr(log, 'INFO'))
amqp_host = config.get('amqp', 'host')
amqp_endpoint = "http://%s:15672/api" % amqp_host

def setup_module():
    pass

def teardown_module():
    pass

_test_data = [
    ('add', 'host', '3548290-5423523'),
    ('change', 'host', '3548290-5423523'),
    ('delete', 'host', '3548290-5423523'),
    ('change', 'network', '89202-292-2942'),
]

def _setup_consumer(ev):
    """
    Starts consumer I/O loop.
    """
    username = config.get('amqp', 'username')
    password = config.get('amqp', 'password')
    credentials = pika.PlainCredentials(username=username, password=password)
    state = {'idx': 0}

    def before_consuming():
        ev.set()

    def consume_msg(ch, method, properties, body):
        log.info('[%s] Consumer received message %s',
                threading.currentThread().getName(), body)
        in_msg = json.loads(body)
        change_type, obj_type, obj_id = _test_data[state['idx']]
        assert in_msg['change_type'] == change_type
        assert in_msg['obj_type'] == obj_type
        assert in_msg['obj_id'] == obj_id
        state['idx'] += 1
        if state['idx'] >= len(_test_data):
            channel = state['channel']
            assert isinstance(channel, pika.channel.Channel)
            channel.close()
            connection = state['connection']
            assert isinstance(connection, pika.connection.Connection)
            connection.close()

    recv_keys = ['*.*.*']
    log.info("Starting consumer IO loop ...")
    io_loop(host=config.get('amqp', 'host'),
            credentials=credentials,
            exch_name='pf9-changes',
            exch_type='topic',
            recv_keys=recv_keys,
            state=state,
            before_processing_msgs_cb=before_consuming,
            consume_cb=consume_msg,
            virtual_host=config.get('amqp', 'virtual_host'))

class TestNotifier(TestCase):
    """
    Test change publisher
    """

    def setUp(self):
        vhost.prep_amqp_broker(config, log, amqp_endpoint)

    def tearDown(self):
        vhost.clean_amqp_broker(config, log, amqp_endpoint)

    def test_publisher(self):
        log.info('Starting test %s:%s', self.__class__, __name__)
        ev = threading.Event()
        thread_id = 'change_consumer'
        t = threading.Thread(name=thread_id,
                             target=_setup_consumer,
                             args=(ev,))
        t.daemon = True
        t.start()
        notifier.init(log, config)
        # Wait for consumer to enter its IO loop, then give it one
        # more second to make sure it's ready to consume messages
        ev.wait(5)
        time.sleep(1)
        for change_type, obj_type, obj_id in _test_data:
            notifier.publish_notification(change_type,
                                          obj_type,
                                          obj_id)
        t.join(10)
        assert not t.isAlive()

