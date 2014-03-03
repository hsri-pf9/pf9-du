# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'leb'

import json
from bbslave import constants
from ConfigParser import ConfigParser
import pika
from pika.channel import Channel

config = ConfigParser()
config.read(constants.CONFIG_FILE)

connection = pika.BlockingConnection(pika.ConnectionParameters(
    host=config.get('amqp', 'host'), credentials=pika.PlainCredentials(
        username=config.get('amqp', 'username'),
        password=config.get('amqp', 'password')
)))
channel = connection.channel()

channel.exchange_declare(exchange=constants.BBONE_EXCHANGE, type='direct')

assert isinstance(channel, Channel)

msg1 = {
    'opcode': 'set_config',
    'data': {
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
    }
}

msg2 = {
    'opcode': 'set_config',
    'data': {
    }
}

msg3 = {
    'opcode': 'set_config',
    'data': {
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
    }
}

msg4 = {
    'opcode': 'set_config',
    'data': {
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
    }
}

msg5 = {
    'opcode': 'set_config',
    'data': {
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
        },
    }
}

# Currently used for manual testing.
# Manually change the message body passed.
channel.basic_publish(exchange=constants.BBONE_EXCHANGE,
                      routing_key=constants.BROADCAST_TOPIC,
                      body=json.dumps(msg1))

