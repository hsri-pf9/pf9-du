# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

"""
This module is implementation of the backbone provider interface.
"""

from ConfigParser import ConfigParser
import datetime
from bbone_provider_memory import bbone_provider_memory
import threading
from bbcommon import constants
from bbcommon.amqp import io_loop
from bbcommon.exceptions import HostNotFound
from bbcommon.utils import is_satisfied_by, get_ssl_options
import base64
import logging
import json
import os
import pika
import requests
import socket
import time
import copy
from pf9_comms import get_comms_cfg, insert_comms, remove_comms
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
        bbmaster_conf = os.environ.get('BBMASTER_CONFIG_FILE',
                                       constants.BBMASTER_CONFIG_FILE)
        self.config.read(bbmaster_conf)
        self.log = logging.getLogger('bbmaster')
        self.retry_period = int(self.config.get('bbmaster',
                                                'connection_retry_period'))
        self.send_pending_msgs_period = int(self.config.get('bbmaster',
                                            'send_pending_msgs_period'))
        self.support_dir_location = self.config.get('bbmaster',
                                                    'support_file_store')
        self.pending_msgs = []
        comms_basedir = self.config.get('bbmaster', 'comms_basedir') if \
            self.config.has_option('bbmaster', 'comms_basedir') else \
            '/opt/pf9/www/private'
        comms_baseurl = self.config.get('bbmaster', 'comms_baseurl') if \
            self.config.has_option('bbmaster', 'comms_baseurl') else \
            'https://%(host_relative_amqp_fqdn)s:9443/private'
        self.slack_attempts = self.config.getint('slack', 'max_posts') if \
            self.config.has_option('slack', 'max_posts') else 5

        self.comms_cfg = get_comms_cfg(self.log, basedir=comms_basedir,
                                       baseurl=comms_baseurl)
        t = threading.Thread(target=self._io_thread)
        t.daemon = True
        t.start()

    # ----- these methods execute in an arbitrary http server thread -----

    def request_support_bundle(self, host_id):
        self._send_msg(host_id, {'opcode': 'get_support'})

    def run_support_command(self, host_id, command):
        msg = {'opcode' : 'support_command',
               'command' : command}
        self._send_msg(host_id, msg)

    def get_host_ids(self):
        # thread safe (I think!)
        return super(bbone_provider_pf9, self).get_host_ids()

    def get_hosts(self, id_list=[], show_comms=False):
        """
        Returns existing host(s)
        """
        with self.lock:
            hosts = super(bbone_provider_pf9, self).get_hosts(id_list)
            return hosts if show_comms else remove_comms(copy.deepcopy(hosts))

    def set_host_apps(self, id, desired_apps):
        """
        Sets the desired apps configuration for a particular host
        """
        with self.lock:
            previous_desired_apps = self.desired_apps.get(id)
            insert_comms(desired_apps, self.comms_cfg)
            super(bbone_provider_pf9, self).set_host_apps(id, desired_apps)
            host_state = self.hosts[id]
        try:
            self._converge_host_if_necessary(host_state, desired_apps)
        except AttributeError:
            # is_satisfied_by() throws AttributeError if desired_apps not a dict
            self.log.error('Invalid app config: %s', desired_apps)
            self.desired_apps[id] = previous_desired_apps

    def get_host_agent(self, host_id):
        """
        Get the details of the host agent on a particular host
        :param str host_id: ID of the host
        :return: dictionary of the host agent information
        :rtype: dict
        """
        with self.lock:
            return super(bbone_provider_pf9, self).get_host_agent(host_id)

    def set_host_agent(self, host_id, agent_data):
        """
        Update the host agent on a particular host
        :param str host_id: ID of the host
        :param dict agent_data: Information about the new host agent. This includes
        URL, name and version for the host agent rpm.
        """
        if host_id not in self.hosts:
            self.log.error('Host %s is not present in the identified '
                           'hosts list.', host_id)
            raise HostNotFound()

        body = {'opcode': 'set_agent', 'data': agent_data}
        # TODO: Think if this should be done with a retry logic
        self._send_msg(host_id, body)

    def post_to_slack(self, msg):
        """
        Post messages to #bbmaster on Slack
        """
        if self.slack_attempts <= 0:
            self.log.warn('Could not post message to Slack: %s '
                          'Maximum number of Slack posts reached'
                          % str(msg))
            return
        if (not self.config.has_option('slack', 'enabled') or
                not self.config.getboolean('slack', 'enabled')):
            return
        url = 'https://hooks.slack.com/services/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'
        json_body = json.dumps({'text' : msg, 'username' : socket.getfqdn()})
        try:
            resp = requests.post(url, data=json_body)
        except:
            self.log.error('Failed to send request to the Slack bbmaster webhook')
            return

        if resp.status_code == requests.codes.ok:
            self.slack_attempts -= 1
        else:
            self.log.error('Sending slack message failed. HTTP error code: %s'
                           % resp.status_code)

    # ----- these methods execute in the I/O thread -----

    def _io_thread(self):
        """
        Continually initiates connections to the broker, retrying upon failure.
        """
        def consume_msg(ch, method, properties, body):
            try:
                body = json.loads(body)
                if body['opcode'] == 'support':
                    handle_support_bundle(body)
                    return
                if body['opcode'] == 'support_command_response':
                    handle_support_command_response(body['data'])
                    return
                if body['opcode'] != 'status':
                    self.log.error('Unknown opcode: %s', body['opcode'])
                    raise ValueError()
                self.log.info('Received: %s', body)
                host_state = body['data']
                host_state['timestamp'] = datetime.datetime.utcnow().\
                                          strftime("%Y-%m-%d %H:%M:%S.%f")
                id = host_state['host_id']
                host_agent_state = host_state['host_agent']
            except (ValueError, TypeError, KeyError):
                self.log.error('Malformed message: %s', body)
                return
            with self.lock:
                self.hosts[id] = host_state
                super(bbone_provider_pf9, self).set_host_agent_config(id, host_agent_state)
                desired_apps = self.desired_apps.get(id)
            self._converge_host_if_necessary(host_state, desired_apps)

        def handle_support_bundle(msg):
            """
            Evaluate the support msg on the broker and write the support file
            """
            self.log.info('Received support file from %s', msg['data']['info'])
            if msg['status'] == 'error':
                self.log.error('Support bundle generation failed %s',
                               msg['error_message'])
                return

            # Currently, msg['status'] can only be success or error. Below
            # would be the success case.
            time_now = datetime.datetime.now()
            host_name = msg['data']['info']['hostname']
            host_id = msg['data']['host_id']
            out_dir = os.path.join(self.support_dir_location, host_id)
            if not os.path.exists(out_dir):
                os.makedirs(out_dir)
            outfile = os.path.join(out_dir, '%s-%s.tgz' % (host_name,
                                   time_now.strftime("%Y-%m-%d-%H-%M-%S")))
            outfile_temp = outfile + '.part'
            try:
                with open(outfile_temp, 'wb') as f:
                    f.write(base64.b64decode(msg['data']['contents']))
                os.rename(outfile_temp, outfile)
            except:
                self.log.exception('Writing out support bundle failed')

        def handle_support_command_response(data):
            """
            Log the support command response to the bbmaster log file.
            """
            self.log.info('Received support commmand response from %s',
                          data['info'])
            if data['status'] == 'error':
                self.log.error('Support command failed %s',
                               data['error_message'])
                return
            # Currently, data['status'] can only be success or error. Below
            # would be the success case.
            self.log.info("Return code: %s" % data['rc'])
            self.log.info("stdout: %s" % data['out'])
            self.log.info("stderr: %s" % data['err'])

        def ping_slaves():
            self._send_msg(constants.BROADCAST_TOPIC, {'opcode': 'ping'})
            send_pending_msgs()

        def send_pending_msgs():
            """
            Periodically sends outgoing messages that have been queued.
            """
            for key in ('connection', 'channel'):
                if key not in self.state:
                    self.log.warn('send_pending_msgs(): %s is down.' % key)
                    return
            with self.lock:
                pending_msgs = self.pending_msgs
                self.pending_msgs = []
            for routing_key, body in pending_msgs:
                self.log.info('Sending to %s : %s', routing_key, body)
                self.state['channel'].basic_publish(
                    exchange=constants.BBONE_EXCHANGE,
                    routing_key=routing_key,
                    body=json.dumps(body))
            self.state['connection'].add_timeout(self.send_pending_msgs_period,
                                                 send_pending_msgs)

        def channel_close_cb(reply_text):
            msg = 'Channel closed due to %s' % reply_text
            self.post_to_slack(msg)

        amqp_username = self.config.get('amqp', 'username') if \
                 self.config.has_option('amqp', 'username') else 'bbmaster'
        amqp_password = self.config.get('amqp', 'password') if \
                 self.config.has_option('amqp', 'password') else 'bbmaster'
        credentials = pika.PlainCredentials(username=amqp_username,
                                            password=amqp_password)
        virt_host = self.config.get('amqp', 'virtual_host') if \
                 self.config.has_option('amqp', 'virtual_host') else None
        ssl_options = get_ssl_options(self.config)
        while True:
            self.state = {}
            try:
                self.log.info("Setting up master io loop, vhost=%s" % virt_host)
                io_loop(log=self.log,
                        host=self.config.get('amqp', 'host'),
                        credentials=credentials,
                        exch_name=constants.BBONE_EXCHANGE,
                        recv_keys=[constants.MASTER_TOPIC],
                        queue_name=constants.BBMASTER_QUEUE,
                        state=self.state,
                        before_processing_msgs_cb=ping_slaves,
                        consume_cb=consume_msg,
                        virtual_host=virt_host,
                        ssl_options=ssl_options,
                        channel_close_cb=channel_close_cb
                        )

            except AMQPConnectionError as e:
                self.log.error('Connection error "%s". Retrying in %d seconds.',
                               e, self.retry_period)
            except IndexError:
                msg = ('Unexpected IndexError. Closing the connection and '
                       'retrying in %d seconds.' % self.retry_period)
                self.log.exception(msg)
                self.post_to_slack(msg)
            except:
                self.log.exception('Unexpected exception in IO thread. ' +
                                   'Closing the connection and retrying ' +
                                   'in %d seconds.',
                                   self.retry_period)
            try:
                # Close the connection in case it was not closed properly
                if 'connection' in self.state:
                    self.state['connection'].close()
                # Sleep in order to avoid spinnng too fast
                time.sleep(self.retry_period)
            except:
                self.log.warn('Failed to clean up connection after exception in io_loop')


    # ----- these execute in either I/O or http threads -----


    def _send_msg(self, routing_key, body):
        """
        Queues a message to be sent. If sending a message to a host,
        ensures that the queue is declared before sending.
        """
        def append_pending_msg():
            with self.lock:
                self.pending_msgs.append((routing_key, body))

        def declare_bbslave_q(host_id):
            """
            Declare a queue for the host. Also, bind it to the bbone exchange.
            These queues are deleted when the server restarts.
            """
            def on_bbslave_queue_bind(method_frame):
                append_pending_msg()

            def on_bbslave_queue_declare(method_frame):
                routing_key_to_bind = routing_keys_to_bind.pop(0)
                callback = on_bbslave_queue_declare if routing_keys_to_bind else on_bbslave_queue_bind
                self.state['channel'].queue_bind(exchange=constants.BBONE_EXCHANGE,
                                                 queue=queue_name,
                                                 routing_key=routing_key_to_bind,
                                                 callback=callback)

            if 'channel' not in self.state:
                self.log.error('declare_bbslave_q(): channel is down.')
                raise RuntimeError('declare_bbslave_q(): channel is down.')
            routing_keys_to_bind = [constants.BROADCAST_TOPIC, host_id]
            queue_name = constants.HOSTAGENT_QUEUE_PREFIX + host_id
            self.state['channel'].queue_declare(queue=queue_name,
                                                callback=on_bbslave_queue_declare)
        if routing_key != constants.BROADCAST_TOPIC:
            # Routing key is a host_id
            #
            # Since declaring the queue is async, we will add to
            # pending_msgs in a callback.
            declare_bbslave_q(routing_key)
        else:
            append_pending_msg()

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
