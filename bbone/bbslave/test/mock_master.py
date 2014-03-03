# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

"""
Simulates a backbone master sending messages to slaves.
To use, connect a single slave to an isolated AMQP broker.
The slave is assumed to use the broker specified at constants.CONFIG_FILE.
Then, start this test.
"""

__author__ = 'leb'

import json
from bbcommon import constants
from ConfigParser import ConfigParser
import pika
from pika.channel import Channel
import time

test_data = [
    {
        'foo': {
            'version': '1.0',
            'url': 'http://foo-1.0.rpm',
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
        },
    },
    {

    },
    {
        'foo': {
            'version': '1.5',
            'url': 'http://foo-1.0.rpm',
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
        },
        'bar': {
            'version': '1.0',
            'url': 'http://bar-1.0.rpm',
            'running': False,
            'config': {
                'xx': {
                    'f':1,
                    'g':2
                },
            }
        }
    },
    {
        'ostackhost': {
            'version': '1.8',
            'url': 'http://www.foo.com/ostackhost-1.0.rpm',
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
        },
        'bar': {
            'version': '1.0',
            'url': 'http://bar-1.0.rpm',
            'running': False,
            'config': {
                'xx': {
                    'f':1,
                    'g':2
                },
            }
        }
    },
    {
        'ostackhost': {
            'version': '1.8',
            'url': 'http://www.foo.com/ostackhost-1.0.rpm',
            'running': False,
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
]

test_data2 = [
    {
        'foo': {
            'version': '1.0',
            'url': 'http://foo-1.0.rpm',
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
]

config = ConfigParser()
config.read(constants.AMQP_CONFIG_FILE)

def test_slave_config_ops():

    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=config.get('amqp', 'host'), credentials=pika.PlainCredentials(
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
    # channel.queue_bind(exchange=constants.BBONE_EXCHANGE,
    #                  queue=queue_name,
    #                  routing_key=constants.MASTER_TOPIC)

    for apps_config in test_data:
        msg = {
            'opcode': 'set_config',
            'data': apps_config
        }
        channel.basic_publish(exchange=constants.BBONE_EXCHANGE,
                              routing_key=constants.BROADCAST_TOPIC,
                              body=json.dumps(msg))
        # method_frame, header_frame, body = channel.basic_get(queue_name)
        # print 'Received: %s'  % body

        # This seems necessary to work around what looks like a data corruption
        # bug when messages are published too quickly: the consumer gets a 505
        # UNEXPECTED_FRAME error. Possible pika bug.
        time.sleep(1)
    channel.close()
    connection.close()

def test_slave_config_ops_async():

    def on_open(connection):
        connection.channel(on_channel_open)

    # Step #4
    def on_channel_open(channel):
        def on_exchange_declare(method_frame):
            for apps_config in test_data:
                msg = {
                    'opcode': 'set_config',
                    'data': apps_config
                }
                channel.basic_publish(exchange=constants.BBONE_EXCHANGE,
                                      routing_key=constants.BROADCAST_TOPIC,
                                      body=json.dumps(msg))
            channel.close()
            connection.close()

        channel.exchange_declare(exchange=constants.BBONE_EXCHANGE,
                                 exchange_type='direct',
                                 callback=on_exchange_declare)

    connection = pika.SelectConnection(pika.ConnectionParameters(
        host=config.get('amqp', 'host'), credentials=pika.PlainCredentials(
            username=config.get('amqp', 'username'),
            password=config.get('amqp', 'password'))),
        on_open_callback=on_open
    )

    try:
        connection.ioloop.start()
    except KeyboardInterrupt:
        connection.close()
        # Start the IOLoop again so Pika can communicate, it will stop on its own when the connection is closed
        connection.ioloop.start()
    pass

def test_slave_config_ops_kombu():
    from kombu import Connection, Exchange
    exch = Exchange(constants.BBONE_EXCHANGE, 'direct')
    with Connection(hostname=config.get('amqp', 'host'),
                    userid=config.get('amqp', 'username'),
                    password=config.get('amqp', 'password')) as conn:
        producer = conn.Producer()
        for apps_config in test_data:
            msg = {
                'opcode': 'set_config',
                'data': apps_config
            }
            producer.publish(body=msg, exchange=exch,
                             routing_key=constants.BROADCAST_TOPIC)

# test_slave_config_ops()
# test_slave_config_ops_async()
test_slave_config_ops_kombu()