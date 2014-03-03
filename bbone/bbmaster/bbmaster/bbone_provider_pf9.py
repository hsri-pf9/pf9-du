# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

"""
This module is implementation of the backbone provider interface.
"""

from ConfigParser import ConfigParser
from bbone_provider_memory import bbone_provider_memory
import threading
from kombu import Connection, Exchange, Queue, pools
from bbcommon import constants
from bbcommon.utils import is_satisfied_by
import logging
import json


class bbone_provider_pf9(bbone_provider_memory):
    """
    Integrates the backbone master with pf9-hostagent slaves
    """

    # ----- these methods execute in the initial python thread -----

    def __init__(self):
        super(bbone_provider_pf9, self).__init__()
        self.lock = threading.Lock()
        self.config = ConfigParser()
        self.config.read([constants.AMQP_CONFIG_FILE,
                          constants.BBMASTER_CONFIG_FILE])
        self.exch = Exchange(constants.BBONE_EXCHANGE, type='direct',
                        durable=False)
        self.queue = Queue(exchange=self.exch,
                           routing_key=constants.MASTER_TOPIC,
                           exclusive=True)
        log_level_name = self.config.get('bbmaster', 'log_level_name')
        logging.basicConfig(level=getattr(logging, log_level_name))
        self.log = logging.getLogger('bbmaster')

        conn = Connection(hostname=self.config.get('amqp', 'host'),
                          userid=self.config.get('amqp', 'username'),
                          password=self.config.get('amqp', 'password'))

        self.conn_pool = pools.connections[conn]
        self.prod_pool = pools.producers[conn]
        self.ping_all_slaves()
        t = threading.Thread(target=self._consumer_thread)
        t.daemon = True
        t.start()

    def ping_all_slaves(self):
        """
        Announces master's presence to all slaves
        """
        msg = { 'opcode': 'ping' }
        with self.prod_pool.acquire(block=True) as prod:
            # TODO: handle broker downtime/disconnects (see IAAS-132)
            prod.publish(msg, exchange=self.exch,
                         routing_key=constants.BROADCAST_TOPIC)

    # ----- these methods execute in an arbitrary http server thread -----

    def get_host_ids(self):
        # thread safe (I think!)
        return super(bbone_provider_pf9, self).get_host_ids()

    def get_hosts(self, id_list=[]):
        """
        Returns existing host(s)
        """
        with self.lock:
            return super(bbone_provider_pf9, self).get_hosts(id_list)

    def set_host_apps(self, id, desired_apps):
        """
        Sets the desired apps configuration for a particular host
        """
        with self.lock:
            previous_desired_apps = self.desired_apps.get(id)
            super(bbone_provider_pf9, self).set_host_apps(id, desired_apps)
            host_state = self.hosts[id]
        try:
            self._converge_host_if_necessary(host_state, desired_apps)
        except AttributeError:
            # is_satisfied_by() throws AttributeError if desired_apps not a dict
            self.log.error('Invalid app config: %s', desired_apps)
            self.desired_apps[id] = previous_desired_apps

    # ----- these methods execute in the consumer thread -----

    def _consumer_thread(self):
        with self.conn_pool.acquire(block=True) as conn:
            # TODO: handle broker downtime/disconnects (see IAAS-132)
            with conn.Consumer(queues=[self.queue],
                               callbacks=[self.consume_msg],
                               no_ack=True):
                while True:
                    conn.drain_events()

    def consume_msg(self, body, message):
        self.log.debug('Received: %s', body)
        try:
            body = json.loads(body)
            assert body['opcode'] == 'status'
            host_state = body['data']
            id = host_state['host_id']
        except (ValueError, TypeError, KeyError):
            self.log.error('Malformed message: %s', body)
            return
        with self.lock:
            self.hosts[id] = host_state
            desired_apps = self.desired_apps.get(id)
        self._converge_host_if_necessary(host_state, desired_apps)

    # ----- this executes in either consumer or http threads -----

    def _converge_host_if_necessary(self, host_state, desired_apps):
        # TODO: validate desired_apps
        if host_state['status'] != 'converging' and \
            not is_satisfied_by(desired_apps, host_state['apps']):
                msg = {
                    'opcode': 'set_config',
                    'data': desired_apps
                }
                assert isinstance(self.prod_pool, pools.ProducerPool)
                with self.prod_pool.acquire(block=True) as prod:
                    # TODO: handle broker downtime/disconnects (see IAAS-132)
                    prod.publish(msg, exchange=self.exch,
                                 routing_key=host_state['host_id'])

provider = bbone_provider_pf9()
