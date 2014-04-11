# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'leb'

import pika
import json
from bbcommon import constants
from bbcommon.amqp import io_loop
from logging import Logger
from ConfigParser import ConfigParser
from pf9app.app_db import AppDb
from pf9app.app_cache import AppCache
from pf9app.app import RemoteApp
from pf9app.algorithms import process_apps
from pf9app.exceptions import Pf9Exception
from sysinfo import get_sysinfo, get_host_id
from bbcommon.utils import is_satisfied_by, get_ssl_options
from os.path import exists, join
from os import makedirs, unlink

# Cached value of desired configuration.
_sys_info = get_sysinfo()
_host_id = get_host_id()
_desired_config_basedir_path = None
_common_config_path = None
_converge_attempts = 0

def _set_desired_config_basedir_path(config):
    """
    Initializes the path of the base directory that will contain the
    a cached copy of the desired apps configuration.
    :param ConfigParser config: configuration object
    """
    global _desired_config_basedir_path, _common_config_path
    dir_path = config.get('hostagent', 'desired_config_basedir_path') if \
        config.has_option('hostagent', 'desired_config_basedir_path') else \
        '/var/opt/pf9/hostagent'
    _common_config_path = dir_path
    dir_path = join(dir_path, _host_id)
    if not exists(dir_path):
        makedirs(dir_path)
    _desired_config_basedir_path = join(dir_path, 'desired_apps.json')

def _persist_host_id():
    """
    Writes the host ID for the host to a configuration file
    (/var/opt/pf9/hostagent/data.conf)
    """
    data_cfg = ConfigParser()
    data_cfg.set('DEFAULT', 'host_id', _host_id)
    with open(join(_common_config_path, 'data.conf'), 'w') as cf:
        data_cfg.write(cf)

def load_desired_config():
    """
    Returns the deserialized JSON of the persisted desired apps
    configuration file, or None if it doesn't exist.
    """
    if not exists(_desired_config_basedir_path):
        return None
    with open(_desired_config_basedir_path, 'r') as file:
        return json.load(file)

def save_desired_config(log, desired_config):
    """
    Persists the desired apps configuration to a file.
    :param Logger log: The logger
    :param dict desired_config: The desired apps configuration dictionary
    """
    if desired_config is None:
        if exists(_desired_config_basedir_path):
            unlink(_desired_config_basedir_path)
    else:
        try:
            json_str = json.dumps(desired_config, indent=4)
            with open(_desired_config_basedir_path, 'w') as file:
                file.write(json_str)
        except Exception as e:
            log.error('Failed to save desired configuration: %s', e)

def start(config, log, app_db, app_cache, remote_app_class):
    """
    Starts a network session with message broker.
    :param ConfigParser config: configuration object
    :param Logger log: logger object
    :param AppDb app_db: database of local pf9 applications
    :param AppCache app_cache: application download manager
    :param RemoteApp remote_app_class: remote application class
    """

    max_converge_attempts = int(config.get('hostagent', 'max_converge_attempts'))
    heartbeat_period = int(config.get('hostagent', 'heartbeat_period'))
    _set_desired_config_basedir_path(config)
    _persist_host_id()

    # This dictionary holds AMQP variables set by the various nested functions.
    # We need a dictionary because python 2.x lacks the 'nonlocal' keyword
    # that would have allowed nested functions to assign parent (but not global)
    # variables. A dictionary is a work-around, since dictionary items can
    # be written without having write access to the dictionary variable itself.
    state = {}

    # ------------ nested functions ------------------

    def get_current_config():
        """
        Computes the current application configuration.
        :return: a dictionary representing the aggregate app configuration.
        :rtype: dict
        """
        apps = app_db.query_installed_apps()
        config = {}
        for app_name, app in apps.iteritems():
            config[app_name] = {
                'version': app.version,
                'running': app.running,
                'config': app.get_config()
            }
        return config

    def send_status(status, config, desired_config=None):
        """
        Sends a message to the master.
        :param str status: Status: 'ok', 'converging', 'retrying', 'failed'
        :param dict config: Current application configuration
        """
        msg = {
            'opcode': 'status',
            'data': {
                'host_id': _host_id,
                'status': status,
                'info': _sys_info,
                'apps': config
            }
        }
        if desired_config is not None:
            msg['data']['desired_apps'] = desired_config
        channel = state['channel']
        channel.basic_publish(exchange=constants.BBONE_EXCHANGE,
                              routing_key=constants.MASTER_TOPIC,
                              body=json.dumps(msg))

    def valid_and_converged(desired_config):
        """
        Checks if desired configuration is valid, and if so, returns
        whether the current configuration already satisfies it.
        :rtype: bool
        """
        assert desired_config is not None
        return process_apps(app_db, app_cache, remote_app_class,
                           desired_config, probe_only=True, log=log) == 0

    def handle_msg(msg):
        """
        Handles an incoming message, which can be an internal heartbeat.
        :param dict msg: message deserialized from JSON
        """
        global _converge_attempts
        desired_config = load_desired_config()
        try:
            if msg['opcode'] not in ('ping', 'heartbeat', 'set_config'):
                log.error('Invalid opcode: %s', msg['opcode'])
                return
            current_config = get_current_config()
            if msg['opcode'] == 'set_config':
                desired_config = msg['data']
                _converge_attempts = 0
            else:
                if msg['opcode'] == 'ping':
                    log.info('Received ping message')
                if desired_config is None:
                    desired_config = current_config
            converged = valid_and_converged(desired_config)
        except (TypeError, KeyError):
            log.error('Malformed message or app config: %s', msg)
            return

        # ok to commit to disk now
        save_desired_config(log, desired_config)
        assert converged == is_satisfied_by(desired_config, current_config)
        if converged:
            log.info('Already converged. Idling...')
            send_status('ok', current_config)
            return

        if _converge_attempts >= max_converge_attempts:
            log.info('In failed state until next set_config message...')
            send_status('failed', current_config, desired_config)
            return

        log.info('--- Converging ---')
        send_status('converging', current_config, desired_config)
        _converge_attempts += 1
        try:
            process_apps(app_db, app_cache, remote_app_class,
                         desired_config, log=log)
        except Pf9Exception as e:
            log.error('Exception during apps processing: %s', type(e))
        current_config = get_current_config()

        converged = valid_and_converged(desired_config)
        if converged:
            assert is_satisfied_by(desired_config, current_config)
            status = 'ok'
            # TODO: update AMQP subscriptions to include app-specific topics
            log.info('Converge succeeded')
            desired_config = None
        else:
            # TODO: increase heartbeat period when retrying, up to a limit
            if _converge_attempts >= max_converge_attempts:
                log.error('Entering failed state after %d converge attempts',
                          _converge_attempts)
                status = 'failed'
            else:
                status = 'retrying'
            log.info('Converge failed')
        send_status(status, current_config, desired_config)

    def consume_msg(ch, method, properties, body):
        handle_msg(json.loads(body))

    def heartbeat(*args, **kwargs):
        connection = state['connection']
        handle_msg({'opcode': 'heartbeat'})
        connection.add_timeout(heartbeat_period, heartbeat)

    credentials = pika.PlainCredentials(username='guest',
                                        password='m1llenn1umFalc0n')
    recv_keys = [constants.BROADCAST_TOPIC, _host_id]
    vhost = None
    try:
        vhost = config.get('amqp', 'virtual_host')
        log.info("Using virtual host %s on the AMQP broker", vhost)
    except:
        # If virtual host is not defined, leave it as None
        log.info("Using the default virtual host '/' on the AMQP broker")

    ssl_options = get_ssl_options(config)
    io_loop(host=config.get('amqp', 'host'),
            credentials=credentials,
            exch_name=constants.BBONE_EXCHANGE,
            recv_keys=recv_keys,
            state=state,
            before_processing_msgs_cb=heartbeat,
            consume_cb=consume_msg,
            virtual_host=vhost,
            ssl_options=ssl_options
            )
