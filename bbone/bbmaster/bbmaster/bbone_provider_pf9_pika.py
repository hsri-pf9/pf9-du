# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

"""
This module is implementation of the backbone provider interface.
"""

from ConfigParser import ConfigParser
from bbone_provider_memory import bbone_provider_memory
import threading
from bbcommon import constants
from bbcommon.amqp import io_loop
from bbcommon.utils import is_satisfied_by, get_ssl_options
import logging
import json
import pika
import time
from os import environ
from pika.exceptions import AMQPConnectionError

class bbone_provider_pf9(bbone_provider_memory):
    """
    Integrates the backbone master with pf9-hostagent slaves
    """

    # ----- these methods execute in the initial python thread -----

    def __init__(self):
        super(bbone_provider_pf9, self).__init__()
        self.lock = threading.Lock()
        self.config = ConfigParser()
        bbmaster_conf = environ.get('BBMASTER_CONFIG_FILE',
                                    constants.BBMASTER_CONFIG_FILE)
        self.config.read(bbmaster_conf)
        log_level_name = self.config.get('bbmaster', 'log_level_name')
        self.log = logging.getLogger('bbmaster')
        self.log.setLevel(getattr(logging, log_level_name))
        self.retry_period = int(self.config.get('bbmaster',
                                                'connection_retry_period'))
        self.send_pending_msgs_period = int(self.config.get('bbmaster',
                                            'send_pending_msgs_period'))
        self.pending_msgs = []
        t = threading.Thread(target=self._io_thread)
        t.daemon = True
        t.start()

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

    # ----- these methods execute in the I/O thread -----

    def _io_thread(self):
        """
        Continually initiates connections to the broker, retrying upon failure.
        """
        def consume_msg(ch, method, properties, body):
            self.log.info('Received: %s', body)
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

        def ping_slaves():
            self._send_msg(constants.BROADCAST_TOPIC, {'opcode': 'ping'})
            send_pending_msgs()

        def send_pending_msgs():
            """
            Periodically sends outgoing messages that have been queued.
            """
            with self.lock:
                pending_msgs = self.pending_msgs
                self.pending_msgs = []
            for routing_key, body in pending_msgs:
                self.log.info('Sending to %s : %s', routing_key, body)
                state['channel'].basic_publish(
                    exchange=constants.BBONE_EXCHANGE,
                    routing_key=routing_key,
                    body=json.dumps(body))
            state['connection'].add_timeout(self.send_pending_msgs_period,
                                            send_pending_msgs)

        credentials = pika.PlainCredentials(username='guest',
                                            password='m1llenn1umFalc0n')
        virt_host = self.config.get('amqp', 'virtual_host') if \
                 self.config.has_option('amqp', 'virtual_host') else None
        ssl_options = get_ssl_options(self.config)
        while True:
            state = {}
            try:
                self.log.info("Setting up master io loop, vhost=%s" % virt_host)
                io_loop(host=self.config.get('amqp', 'host'),
                        credentials=credentials,
                        exch_name=constants.BBONE_EXCHANGE,
                        recv_keys=[constants.MASTER_TOPIC],
                        state=state,
                        before_processing_msgs_cb=ping_slaves,
                        consume_cb=consume_msg,
                        virtual_host=virt_host,
                        ssl_options=ssl_options
                        )

            except AMQPConnectionError as e:
                self.log.error('Connection error "%s". Retrying in %d seconds.',
                               e, self.retry_period)
                time.sleep(self.retry_period)


    # ----- these execute in either I/O or http threads -----

    def _send_msg(self, routing_key, body):
        """
        Queues a message to be sent
        """
        with self.lock:
            self.pending_msgs.append((routing_key, body))

    def _converge_host_if_necessary(self, host_state, desired_apps):
        """
        Sends a host a set_config message if one of these conditions is true:
        1) Host is in ok state, but with an undesired current configuration.
        2) Host is in converging, retrying or failed state while attempting to
           converge towards an undesired configuration.
        The current assumption is if a host is in a failed state after trying
        to converge towards the desired configuration, an extraordinary action
        possibly involving human intervention is required to get it out of that
        state. This action could be, for example, resetting a the desired
        configuration to a different value, e.g. the empty configuration {}.
        :param dict host_state: The host's last known configuration
        :param dict desired_apps: The desired apps configuration for the host
        """
        status = host_state['status']
        converging_to = host_state.get('desired_apps')
        if (status == 'ok' and not is_satisfied_by(desired_apps, host_state['apps'])) \
             or (status != 'ok' and converging_to is not None and not
                    is_satisfied_by(desired_apps, converging_to)):
            body = {'opcode': 'set_config', 'data': desired_apps}
            self._send_msg(host_state['host_id'], body)

provider = bbone_provider_pf9()
