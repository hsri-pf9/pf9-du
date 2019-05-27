# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

"""
Simulates a backbone master receiving messages from slaves.
To use, connect a single slave to an isolated AMQP broker.
The slave is assumed to use the broker specified at constants.CONFIG_FILE.
Then, start this test.
"""

__author__ = 'leb'

import json
from bbslave import constants
from six.moves.configparser import ConfigParser
import pika
from pika.channel import Channel
import time


def receive_messages():

    config = ConfigParser()
    config.read(constants.CONFIG_FILE)

    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=config.get('amqp_host', 'host'), credentials=pika.PlainCredentials(
            username=config.get('amqp', 'username'),
            password=config.get('amqp', 'password')
    )))
    channel = connection.channel()

    channel.exchange_declare(exchange=constants.BBONE_EXCHANGE,
                             exchange_type='direct')

    assert isinstance(channel, Channel)
    result = channel.queue_declare(exclusive=True)
    queue_name = result.method.queue

    # Subscribe to the broadcast topic for all backbone slaves
    channel.queue_bind(exchange=constants.BBONE_EXCHANGE,
                       queue=queue_name,
                       routing_key=constants.MASTER_TOPIC)

    def consume_msg(ch, method, properties, body):
        print('Received: %s'  % body)

    channel.basic_consume(consume_msg,
                          queue=queue_name,
                          no_ack=True)
    channel.start_consuming()

receive_messages()
