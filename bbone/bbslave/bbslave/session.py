# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'leb'

import os
import base64
import pika
import json
from bbcommon import constants
from bbcommon.amqp import dual_channel_io_loop
from datagatherer import datagatherer
from logging import Logger
from ConfigParser import ConfigParser
from pf9app.app_db import AppDb
from pf9app.app_cache import AppCache
from pf9app.app import RemoteApp
from pf9app.algorithms import process_apps, process_agent_update
from pf9app.exceptions import Pf9Exception
from pf9app.pf9_app import _run_command as pf9_app_run_command
import glob
import subprocess
import datetime
import shlex
import re
from sysinfo import get_sysinfo, get_host_id
from bbcommon.utils import is_satisfied_by, get_ssl_options
from os.path import exists, join
from os import makedirs, rename, unlink, environ
from pika.exceptions import AMQPConnectionError

_host_id = get_host_id()
_desired_config_basedir_path = None
_support_file_location = None
_common_config_path = None
_converge_attempts = 0
_hostagent_info = {}
_allowed_commands_regexes = ['^sudo service pf9-[-\w]+ (stop|start|status|restart)$']

# Dictionary of potentially allowed commands.
# The key is the command string.
# The value specifies whether the command starts a remote ssh session.
_allowed_commands = {
    'rm -rf /var/cache/pf9apps/*': False,
    '/opt/pf9/comms/utils/forward_ssh.sh': True
}

HYPERVISOR_INFO_FILE = '/var/opt/pf9/hypervisor_details'
DEFAULT_ALLOW_REMOTE_SSH_FILE_PATH = '/etc/pf9/allow_remote_ssh'

def _set_desired_config_basedir_path(config):
    """
    Initializes the path of the base directory that will contain the
    a cached copy of the desired apps configuration.
    :param ConfigParser config: configuration object
    """
    global _desired_config_basedir_path, _common_config_path, _support_file_location
    dir_path = config.get('hostagent', 'desired_config_basedir_path') if \
        config.has_option('hostagent', 'desired_config_basedir_path') else \
        '/var/opt/pf9/hostagent'
    _common_config_path = dir_path
    dir_path = join(dir_path, _host_id)
    if not exists(dir_path):
        makedirs(dir_path)
    _desired_config_basedir_path = join(dir_path, 'desired_apps.json')
    _support_file_location = join(dir_path, 'pf9-support.tgz')

def _persist_host_id():
    """
    Writes the host ID for the host to a configuration file
    (/var/opt/pf9/hostagent/data.conf)
    """
    data_cfg = ConfigParser()
    data_cfg.set('DEFAULT', 'host_id', _host_id)
    with open(join(_common_config_path, 'data.conf'), 'w') as cf:
        data_cfg.write(cf)

def _load_host_agent_info(agent_app_db):
    """
    Load the current host agent details. This will be reported back to the
    master as part of status message.
    """
    global _hostagent_info
    if 'HOSTAGENT_VERSION' in environ:
        # Fake version. This comes in handy when testing on a system
        # that does not have the pf9-hostagent package installed
        agent_info = {'version': environ['HOSTAGENT_VERSION']}
    else:
        agent_info = agent_app_db.query_installed_agent()
    _hostagent_info = {
                        'status': 'running',
                        'version': agent_info['version']
                      }

def load_desired_config(log):
    """
    Returns the deserialized JSON of the persisted desired apps
    configuration file, or None if it doesn't exist.
    """
    if not exists(_desired_config_basedir_path):
        return None
    try:
        with open(_desired_config_basedir_path, 'r') as file:
            return json.load(file)
    except Exception as e:
        log.error('Failed to load desired configuration: %s', e)
        return None

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
            # Write to a temporary file to ensure file is not corrupted
            # in case of an unexpected error
            temp_desired_config_basedir_path = _desired_config_basedir_path + '.part'
            with open(temp_desired_config_basedir_path, 'w') as file:
                file.write(json_str)
            rename(temp_desired_config_basedir_path, _desired_config_basedir_path)
        except Exception as e:
            log.error('Failed to save desired configuration: %s', e)


def _run_command(command, log, run_env=environ):
    """
    Runs a command
    :param str command: Command to be executed.
    :return: a tuple representing (code, output), where code is the
    return code of the command, output of the command
    :rtype: tuple
    """
    try:
        out = subprocess.check_output(shlex.split(command), env=run_env)
        # Command was successful, return code must be 0 with relevant output
        return 0, out
    except subprocess.CalledProcessError as e:
        log.error('%s command failed: %s', command, e)
        return e.returncode, e.output


def start(config, log, app_db, agent_app_db, app_cache,
          remote_app_class, agent_app_class,
          channel_retry_period=10):
    """
    Starts a network session with message broker.
    :param ConfigParser config: configuration object
    :param Logger log: logger object
    :param AppDb app_db: database of local pf9 applications
    :param AppDb agent_app_db: database of pf9 host agent
    :param AppCache app_cache: application download manager
    :param RemoteApp remote_app_class: remote application class
    :param type agent_app_class: Agent app class
    :param int channel_retry_period: Channel retry period in seconds
    """

    amqp_host = config.get('amqp', 'host')
    download_protocol = config.get('download', 'protocol')
    download_port = config.get('download', 'port')
    url_interpolations = {
        'host_relative_amqp_fqdn': amqp_host,
        'download_protocol': download_protocol,
        'download_port': download_port
    }
    allow_exit_opcode = config.getboolean('hostagent', 'allow_exit_opcode') if \
        config.has_option('hostagent', 'allow_exit_opcode') else False
    allow_remote_ssh_file_path = config.get('hostagent',
        'allow_remote_ssh_file_path') if config.has_option('hostagent',
        'allow_remote_ssh_file_path') else DEFAULT_ALLOW_REMOTE_SSH_FILE_PATH
    max_converge_attempts = int(config.get('hostagent', 'max_converge_attempts'))
    heartbeat_period = int(config.get('hostagent', 'heartbeat_period'))
    extensions_path = config.get('hostagent', 'extensions_path') if \
        config.has_option('hostagent', 'extensions_path') else '/opt/pf9/hostagent/extensions'
    _load_host_agent_info(agent_app_db)
    _set_desired_config_basedir_path(config)
    _persist_host_id()

    # This dictionary holds AMQP variables set by the various nested functions.
    # We need a dictionary because python 2.x lacks the 'nonlocal' keyword
    # that would have allowed nested functions to assign parent (but not global)
    # variables. A dictionary is a work-around, since dictionary items can
    # be written without having write access to the dictionary variable itself.
    state = {}

    # ------------ nested functions ------------------

    def is_remote_ssh_allowed():
        return os.path.isfile(allow_remote_ssh_file_path)

    def hypervisor_info():
        hypervisor_info = dict()

        # Existence of this file is an indicator of 'VMWareCluster' appliance,
        # instead of conf parameter
        # so that upgrades do not affect this determination
        if os.path.isfile(HYPERVISOR_INFO_FILE):
            hypervisor_info['hypervisor_type'] = 'VMWareCluster'
        else:
            hypervisor_info['hypervisor_type'] = 'kvm'

        return hypervisor_info

    def get_current_config():
        """
        Computes the current application configuration.
        :return: a dictionary representing the aggregate app configuration.
        :rtype: dict
        """
        apps = app_db.query_installed_apps()
        config = {}
        for app_name, app in apps.iteritems():
            if app.implements_service_states:
                config[app_name] = {
                    'version': app.version,
                    'config': app.get_config(),
                    'service_states': app.get_service_states()
                }
            else:
                config[app_name] = {
                    'version': app.version,
                    'running': app.running,
                    'config': app.get_config()
                }
        return config

    def get_extension_data():
        """
        Get data from data extensions of host agent. Runs scripts that
        match a certain filename pattern and are placed in the extensions
        directory
        """
        ext_data = {}
        # Files which need to be run should start with fetch_ or check_
        # prefix.
        file_types = ['fetch_', 'check_']
        for ftype in file_types:
            # Find files that match the pattern
            file_pattern = os.path.join(extensions_path, '%s*' % ftype)
            for fpath in glob.iglob(file_pattern):
                fname, ext = os.path.splitext(os.path.basename(fpath))
                # The script name (without the fetch_ or check_ prefix)
                # is used as a key in the output dict
                try:
                    m = re.search('%s(.+)' % ftype, fname).group(1)
                except AttributeError:
                    # deal with the error here.
                    log.error('File %s does not meet expected extension file '
                              'naming convention', fname)
                    continue

                # Run the command
                rcode, output = _run_command(fpath, log)
                if rcode:
                    # Running the extension failed
                    ext_result = {
                        'status': 'error',
                        'data': output
                    }
                else:
                    try:
                        # Try to build result dict which is JSON serializable
                        ext_result = {
                            'status': 'ok',
                            'data': json.loads(output)
                        }
                    except Exception as e:
                        log.error('Extension data %s is not JSON serializable: %s',
                                  output, e)
                        ext_result = {
                            'status': 'error',
                            'data': 'Extension returned non JSON serializable data'
                        }

                ext_data.update({m: ext_result})

        return ext_data

    def send_status(status, config, desired_config=None):
        """
        Sends a message to the master.
        :param str status: Status: 'ok', 'converging', 'retrying', 'failed'
        :param dict config: Current application configuration
        """
        if 'channel' not in state:
            log.warn('Not sending status message because channel is closed')
            return
        msg = {
            'opcode': 'status',
            'data': {
                'host_id': _host_id,
                'timestamp': datetime.datetime.utcnow().strftime("%Y-%m-%d "
                                                                 "%H:%M:%S.%f"),
                'status': status,
                'info': get_sysinfo(),
                'hypervisor_info': hypervisor_info(),
                'apps': config,
                'host_agent': _hostagent_info,
                'extensions': get_extension_data()
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
                            desired_config, probe_only=True, log=log,
                            url_interpolations=url_interpolations) == 0

    def update_agent(agent_info, current_config, desired_config):
        """
        Trigger an update of the host agent.
        :param dict agent_info: Update info for the agent update
        :param dict current_config: Current app config on the host
        :param dict desired_config: Desired app config for the host
        """
        # Send an updating status for host agent first
        _hostagent_info['status'] = 'updating'
        send_status('ok', current_config, desired_config)
        try:
            # Perform the update
            # Note that the update does an agent restart. On restart the new agent
            # should return a 'running' host agent status with new agent version
            process_agent_update(agent_info, agent_app_db, app_cache,
                                 agent_app_class, log)
        except Pf9Exception:
            # TODO:  Currently we don't retry the update. Consider reporting
            # a failure and retry logic
            log.exception('Updating the pf9 host agent failed')
        else:
            # If the agent update was success, the agent should restart as part
            # of the update and not hit this case. There is a chance that update
            # was reported success but no error code returned. For example, the
            # package manager did not consider the rpm as an update to current
            # host agent
            log.error('Host agent update %s did not happen', agent_info)

        # All error/exception case, reload the host agent info
        _load_host_agent_info(agent_app_db)

    def process_support_request():
        """
        Handle the request to generate the support bundle and send the file
        to the backbone master through rabbitmq broker.
        """
        if 'channel' not in state:
            log.warn('Not sending support bundle because channel is closed')
            return
        msg = {
            'opcode': 'support',
            'data': {
                'host_id': _host_id,
                'info': get_sysinfo(),
            }
        }

        try:
            datagatherer.generate_support_bundle(_support_file_location, log)
            with open(_support_file_location, 'rb') as f:
                # Choose base64 encoding to transfer binary content
                msg['data']['contents'] = base64.b64encode(f.read())
            msg['status'] = 'success'
            msg['error_message'] = ''
        except Exception as e:
            log.exception('Support bundle generation failed.')
            msg['status'] = 'error'
            msg['error_message'] = str(e)
            msg['data']['contents'] = ''

        channel = state['channel']
        log.info('Publishing support bundle message to broker')
        channel.basic_publish(exchange=constants.BBONE_EXCHANGE,
                              routing_key=constants.MASTER_TOPIC,
                              body=json.dumps(msg))

    def process_support_command(command):
        """
        Handle the request to run the support command and send the output
        to the backbone master through rabbitmq broker.
        """
        def _is_command_allowed():
            if command in _allowed_commands:
                is_remote_ssh = _allowed_commands[command]
                return not is_remote_ssh or is_remote_ssh_allowed()
            for regex in _allowed_commands_regexes:
                regex = re.compile(regex)
                if regex.match(command):
                    return True
            return False

        msg = {
            'opcode': 'support_command_response',
            'data': {
                'host_id': _host_id,
                'info': get_sysinfo(),
                'command': command,
            }
        }

        try:
            data = msg['data']
            if _is_command_allowed():
                log.info('Running command: %s' % command)
                # If the command involves the hostagent service,
                # do not capture the stdout due to issues with restarting
                if command.startswith('sudo service pf9-hostagent '):
                    stdout = (None,)
                else:
                    stdout = ()
                data['rc'], data['out'], data['err'] = pf9_app_run_command(command, *stdout)
                log.info('Return code: %s' % data['rc'])
                log.info('stdout: %s' % data['out'])
                log.info('stderr: %s' % data['err'])
                data['status'] = 'success'
                data['error_message'] = ''
            else:
                log.error('Invalid command requested: %s' % command)
                data['status'] = 'error'
                data['error_message'] = 'Invalid command: %s' % command
        except Exception as e:
            log.exception('Support command failed.')
            data['status'] = 'error'
            data['error_message'] = str(e)

        channel = state['channel']
        log.info('Publishing command request message to broker')
        channel.basic_publish(exchange=constants.BBONE_EXCHANGE,
                              routing_key=constants.MASTER_TOPIC,
                              body=json.dumps(msg))
    def handle_msg(msg):
        """
        Handles an incoming message, which can be an internal heartbeat.
        :param dict msg: message deserialized from JSON
        """
        global _converge_attempts
        desired_config = load_desired_config(log)
        try:
            if msg['opcode'] not in ('ping', 'heartbeat', 'set_config',
                                     'set_agent', 'exit', 'get_support',
                                     'support_command'):
                log.error('Invalid opcode: %s', msg['opcode'])
                return
            if msg['opcode'] == 'exit':
                if allow_exit_opcode:
                    log.info('Exiting cleanly.')
                    state['channel'].close()
                    state['connection'].close()
                else:
                    log.error('Unexpected "exit" opcode.')
                return
            current_config = get_current_config()
            if msg['opcode'] == 'set_agent':
                log.info('Received set_agent message')
                if desired_config is None:
                    desired_config = current_config
                update_agent(msg['data'], current_config, desired_config)
                return
            if msg['opcode'] == 'get_support':
                log.info('Received get_support message')
                process_support_request()
                return
            if msg['opcode'] == 'support_command':
                log.info('Received support_command message: %s' % msg['command'])
                process_support_command(msg['command'])
                return
            if msg['opcode'] == 'set_config':
                desired_config = msg['data']
                _converge_attempts = 0
            else:
                if msg['opcode'] == 'ping':
                    log.info('Received ping message')
                if desired_config is None:
                    desired_config = current_config
            converged = valid_and_converged(desired_config)
        except (TypeError, KeyError, Pf9Exception):
            log.exception('Bad message, app config or reading current app '
                          'config. Message : %s', msg)
            return

        # ok to commit to disk now
        save_desired_config(log, desired_config)
        satisfied = is_satisfied_by(desired_config, current_config)
        if converged != satisfied:
            # I've seen this happen when manually deleting / installing
            # pf9 apps out-of-band outside of pf9-hostagent as part of pf9-comms
            # testing. Haven't been able to explain it yet.
            # Make it non-fatal and log a warning for now.  -leb
            log.warn(('Integrity check failed: converged:%s satisfied:%s '+
                      'desired:%s current:%s') % (converged, satisfied,
                                                  desired_config,
                                                  current_config))
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
        if _converge_attempts == max_converge_attempts:
                # This is the last convergence attempt. Generate the support
                # request and send it to the DU as part of the last
                # convergence attempt
                process_support_request()

        try:
            process_apps(app_db, app_cache, remote_app_class,
                         desired_config, log=log,
                         url_interpolations=url_interpolations)
        except Pf9Exception as e:
            log.error('Exception during apps processing: %s', type(e))

        try:
            current_config = get_current_config()
        except Pf9Exception:
            log.exception('Reading current configuration failed.')
            return

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

    def connection_up_cb(connection):
        def _renew_timer():
            heartbeat()
            connection.add_timeout(heartbeat_period, _renew_timer)

        state['connection'] = connection
        log.info('Connected to broker. Starting heartbeat timer.')
        _renew_timer()

    def connection_down_cb(connection):
        state['connection_closed_unexpectedly'] = True
        del state['connection']

    def send_channel_up_cb(channel):
        state['channel'] = channel
        # Send one heartbeat now to announce ourselves to the bbmaster.
        heartbeat()

    def send_channel_down_cb(channel):
        del state['channel']

    def heartbeat():
        handle_msg({'opcode': 'heartbeat'})

    # Process one heartbeat now to try to converge towards cached desired
    # state, regardless of whether we can establish an AMQP connection. This is
    # necessary to restart critical pf9apps like pf9-comms after a reboot.
    heartbeat()
    user = config.get('amqp', 'username') if config.has_option('amqp',
        'username') else 'bbslave'
    password = config.get('amqp', 'password') if config.has_option('amqp',
        'password') else 'bbslave'
    credentials = pika.PlainCredentials(username=user, password=password)
    vhost = None
    try:
        vhost = config.get('amqp', 'virtual_host')
        log.info("Using virtual host %s on the AMQP broker %s",
                 vhost, amqp_host)
    except:
        # If virtual host is not defined, leave it as None
        log.info("Using the default virtual host '/' on the AMQP broker %s",
                 amqp_host)

    ssl_options = get_ssl_options(config)
    queue_name = config.get('amqp', 'queue_name') if config.has_option('amqp',
        'queue_name') else 'bbslave-q-' + _host_id
    socket_timeout = float(config.get('amqp', 'connect_timeout')) \
        if config.has_option('amqp', 'connect_timeout') else 2.5
    dual_channel_io_loop(log,
                         host=amqp_host,
                         credentials=credentials,
                         queue_name=queue_name,
                         retry_timeout=channel_retry_period,
                         connection_up_cb=connection_up_cb,
                         connection_down_cb=connection_down_cb,
                         send_channel_up_cb=send_channel_up_cb,
                         send_channel_down_cb=send_channel_down_cb,
                         consume_cb=consume_msg,
                         virtual_host=vhost,
                         ssl_options=ssl_options,
                         socket_timeout=socket_timeout)  # in secs

    if 'connection_closed_unexpectedly' in state:
        log.error('Connection closed unexpectedly.')
        raise AMQPConnectionError
