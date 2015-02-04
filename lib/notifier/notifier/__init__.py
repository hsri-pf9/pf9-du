# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights Reserved.

import threading
import pika
from logging import Logger
from bbcommon.amqp import io_loop
from bbcommon.utils import get_ssl_options
import time
import json

_EXCH_NAME = 'pf9-changes'
_CONNECTION_RETRY_PERIOD = 5
_SEND_MSGS_PERIOD = 1
_HEARTBEAT_PERIOD = 15
_queue_name = 'pf9-changes-q'
_pending_msgs = []
_lock = threading.Lock()


def _io_thread(log, config):

    def _before_processing_messages():
        """
        Starts two periodic tasks: sending general messages,
        and sending heartbeats
        """
        _heartbeat()
        _send_pending_msgs()

    def _send_pending_msgs():
        """
        Periodically sends queued messages.
        """
        global _pending_msgs
        with _lock:
            pending_msgs = _pending_msgs
            _pending_msgs = []
        for routing_key, body in pending_msgs:
            log.info('Sending %s to %s', body, routing_key)
            state['channel'].basic_publish(
                exchange=_EXCH_NAME,
                routing_key=routing_key,
                body=json.dumps(body))
        state['connection'].add_timeout(_SEND_MSGS_PERIOD, _send_pending_msgs)

    def _heartbeat():
        """
        Periodically sends heartbeat messages.
        This is useful for certain clients, such as buggy web browsers, to
        detect when a connection has gone bad or closed.
        """
        publish_notification('heartbeat', 'none', 'none')
        state['connection'].add_timeout(_HEARTBEAT_PERIOD, _heartbeat)

    username = config.get('amqp', 'username') \
        if config.has_option('amqp', 'username') else 'guest'
    password = config.get('amqp', 'password') \
        if config.has_option('amqp', 'password') else 'm1llenn1umFalc0n'
    credentials = pika.PlainCredentials(username=username, password=password)
    host = config.get('amqp', 'host')
    virt_host = config.get('amqp', 'virtual_host') if \
             config.has_option('amqp', 'virtual_host') else None
    ssl_options = get_ssl_options(config)

    while True:
        state = {}
        try:
            log.info("Setting up changepublisher io loop, vhost=%s" % virt_host)
            io_loop(log=log,
                    queue_name=_queue_name,
                    host=host,
                    credentials=credentials,
                    exch_name=_EXCH_NAME,
                    state=state,
                    before_processing_msgs_cb=_before_processing_messages,
                    exch_type='topic',
                    virtual_host=virt_host,
                    ssl_options=ssl_options
                    )

        except pika.exceptions.AMQPConnectionError as e:
            log.error('AMQP connection error "%s". Retrying in %d seconds.',
                           e, _CONNECTION_RETRY_PERIOD)
            time.sleep(_CONNECTION_RETRY_PERIOD)

def init(log, config):
    """
    Initializes the change publisher by starting its I/O thread.
    :param Logger log: The logger object
    :param ConfigParser config: config object
    """
    t = threading.Thread(target=_io_thread, args=(log, config))
    t.daemon = True
    t.start()

def publish_notification(change_type, obj_type, obj_id):
    """
    Queues a change record for publishing to the message broker.
    :param str change_type: Change type: 'add', 'delete', 'change'
    :param str obj_type: Object type: 'host', etc...
    :param str obj_id: Object ID
    """
    tuple = [change_type, obj_type, obj_id]
    body = {'change_type': change_type, 'obj_type': obj_type, 'obj_id': obj_id}
    # 3-part topic allows consumers to filter
    routing_key = '.'.join(tuple)
    with _lock:
        _pending_msgs.append((routing_key, body))

