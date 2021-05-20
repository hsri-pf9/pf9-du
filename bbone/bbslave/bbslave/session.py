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
from six.moves.configparser import ConfigParser
from pf9app.app_db import AppDb
from pf9app.app_cache import AppCache
from pf9app.app import RemoteApp
from pf9app.algorithms import process_apps, process_agent_update
from pf9app.exceptions import Pf9Exception
from pf9app.pf9_app import _run_command as pf9_app_run_command
import glob
import subprocess
import datetime
import sys
import logging
import shlex
import re
from bbslave import certs
from bbslave import util
from socket import gethostname
from bbslave.sysinfo import get_sysinfo, get_host_id
from bbcommon.utils import is_satisfied_by, get_ssl_options
from os.path import exists, join
from os import makedirs, rename, unlink, environ, listdir
from pika.exceptions import AMQPConnectionError
from six import iteritems
from six.moves import queue as Queue

_host_id = get_host_id()
_desired_config_basedir_path = None
_support_file_location = None
_common_config_path = None
_hostagent_info = {}
_pending_support_bundle = {'pending': False}


HYPERVISOR_INFO_FILE = '/var/opt/pf9/hypervisor_details'


def _handle_iaas_3166(log, disable_iaas_1366_handling, desired_config):
    """
    IAAS-3166: if pf9-comms is installed but not running, set it to running
    state to ensure we can communicate with the DU. This situation can happen if
    pf9-hostagent and pf9-comms packages are installed manually outside of the
    installer, and pf9-hostagent service is started first.
    :param log: logger
    :param disable_iaas_1366_handling: whether to skip this logic
    :param desired_config: the desired configuration to modify
    :return:
    """
    if disable_iaas_1366_handling:
        return
    if 'pf9-comms' in desired_config:
        if 'running' in desired_config['pf9-comms']:
            if not desired_config['pf9-comms']['running']:
                log.info('IAAS-1366: forcing pf9-comms to running state')
                desired_config['pf9-comms']['running'] = True

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
        completed_proc = subprocess.run(shlex.split(command),
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,
                                        check=True)
        # Command was successful, return code must be 0 with relevant output
        return completed_proc.returncode, completed_proc.stdout, completed_proc.stderr
    except subprocess.CalledProcessError as e:
        log.error('%s command failed: %s', command, e)
        return e.returncode, b'{"err_msg" : "' + e.output + b'"}', b''

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

    amqp_host = config.get('amqp_host', 'host')
    download_protocol = config.get('download', 'protocol')
    download_port = config.get('download', 'port')
    url_interpolations = {
        'host_relative_amqp_fqdn': amqp_host,
        'download_protocol': download_protocol,
        'download_port': download_port
    }
    allow_exit_opcode = config.getboolean('hostagent', 'allow_exit_opcode') if \
        config.has_option('hostagent', 'allow_exit_opcode') else False
    max_converge_attempts = int(config.get('hostagent', 'max_converge_attempts'))
    heartbeat_period = int(config.get('hostagent', 'heartbeat_period'))
    extensions_path = config.get('hostagent', 'extensions_path') if \
        config.has_option('hostagent', 'extensions_path') else '/opt/pf9/hostagent/extensions'
    disable_iaas_1366_handling = config.get('hostagent', 'disable_iaas_1366_handling') if \
        config.has_option('hostagent', 'disable_iaas_1366_handling') else False
    _load_host_agent_info(agent_app_db)
    _set_desired_config_basedir_path(config)
    _persist_host_id()

    # This dictionary holds AMQP variables set by the various nested functions.
    # We need a dictionary because python 2.x lacks the 'nonlocal' keyword
    # that would have allowed nested functions to assign parent (but not global)
    # variables. A dictionary is a work-around, since dictionary items can
    # be written without having write access to the dictionary variable itself.
    state = {'converge_attempts': 0}

    # ------------ nested functions ------------------

    def load_allowed_commands():
        """
        Scan a well known location and load files to match allowed commands.
        This is an extensible mechanism, packages installed with hostagent
        can add new commands as needed.
        :return: A dictionary of allowed commands.
        """
        # Dictionary of potentially allowed commands.
        #  The key is the regular expression of the command.
        #  The value, if not None, is a callback that returns a boolean
        #  indicating whether the command is allowed.

        allowed_cmd_patterns = []
        support_cmd_drop_dir = config.get('hostagent', 'allowed_commands_dir')

        files = [join(support_cmd_drop_dir, f) for f in listdir(support_cmd_drop_dir)
                 if os.path.isfile(join(support_cmd_drop_dir, f))]

        for f in files:
            with open(f) as fh:
                for l in fh.readlines():
                    line = l.strip()
                    if not line:
                        continue
                    allowed_cmd_patterns.append(line)

        log.debug('Support command patterns: %s', allowed_cmd_patterns)
        return allowed_cmd_patterns


    def hypervisor_info():
        hypervisor_info = dict()

        # Existence of this file is an indicator of VMWare appliance,
        # instead of conf parameter so that upgrades do not affect this determination
        # The type listed in this file is used to determine if its Gateway appliance or Network node.
        if os.path.isfile(HYPERVISOR_INFO_FILE):
            try:
                with open(HYPERVISOR_INFO_FILE, 'r') as host_details:
                   hypervisor_info['hypervisor_type'] = json.loads(host_details.read()).get('hypervisor_type', 'VMWareCluster')
            except Exception as e:
                log.error('Setting default vmware hypervisor type as VMWareCluster due to: %s' % e)
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
        log.debug('get_current_config begin')
        config = app_db.get_current_config()
        log.debug('get_current_config end')
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

                if not os.access(fpath, os.X_OK):
                    # The file doesn't have execute permissions, skip it
                    continue

                # Run the command
                try:
                    #Timeout after 20s if the extension has failed to finish
                    command = 'timeout 120 ' + fpath
                    rcode, output, err = _run_command(command, log)
                    if err:
                        log.warn('Extension returned data in stderr : {}'.format(err))
                except Exception as e:
                    msg = 'Error running extension script: %s' % e
                    log.error(msg)
                    # Setting rcode to an invalid system exit code value here
                    # just to ensure it is processed in below return structure.
                    rcode = 256
                    output = msg

                if rcode:
                    #Execution of command has timed-out.
                    if rcode == 124:
                        ext_result = {
                            'status': 'timed-out',
                            'data': 'Extension script timed-out'
                        }
                    else:
                        # Running the extension failed
                        # Check for blank output in byte format.
                        if output == b'':
                            data = ""
                        else:
                            data = json.loads(output.decode(), strict=False)

                        ext_result = {
                            'status': 'error',
                            'data': data
                        }
                else:
                    try:
                        # Try to build result dict which is JSON serializable
                        ext_result = {
                            'status': 'ok',
                            # Python3: JSON object cannot be 'bytes'. It has to be a string.
                            'data': json.loads(output.decode())
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
                'status': status,
                'info': get_sysinfo(log),
                'hypervisor_info': hypervisor_info(),
                'apps': config,
                'host_agent': _hostagent_info,
                'extensions': get_extension_data()
            }
        }

        if util.vouch_present:
            # Check if cert data is available on the queue
            msg['data']['cert_info'] = util.check_for_cert_data(log)

        if desired_config is not None:
            msg['data']['desired_apps'] = desired_config

        channel = state['channel']
        timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%d '
                                                        '%H:%M:%S.%f')
        msg['data']['timestamp'] = timestamp
        channel.basic_publish(exchange=constants.BBONE_EXCHANGE,
                              routing_key=constants.MASTER_TOPIC,
                              body=json.dumps(msg))

    def valid_and_converged(current_config, desired_config):
        """
        Checks if desired configuration is valid, and if so, returns
        whether the current configuration already satisfies it.
        :rtype: bool
        """
        assert desired_config is not None
        return process_apps(app_db, app_cache, remote_app_class,
                            desired_config, probe_only=True, log=log,
                            current_config=current_config,
                            url_interpolations=url_interpolations) == 0

    def close_fds():
        '''
        Flush and close all possible file descriptors for this process
        '''
        try:
            maxfd = os.sysconf("SC_OPEN_MAX")
        except:
            # Assume 256 fds
            maxfd = 256

        for fd in range(3, maxfd):
            try:
                os.fsync(fd)
                os.close(fd)
            except OSError:
                pass

    def reboot_agent():
        '''
        Reboot host agent. Needed when the host agent updates itself.
        '''
        # Flush the stdout and stderr buffers are flushed so that all relevant
        # logs are written out before the restart.
        # TODO: stdout and stderr need to be explicitly flushed and don't behave
        # well when done as part of the flush_fds method. Need to figure out why.
        log.warn("Launching %s as %s", sys.argv[0], sys.argv)
        sys.stdout.flush()
        sys.stderr.flush()
        # Perform a clean shutdown of the loggers, before closing all the fds.
        # Otherwise the logger gets messed up on respawn of the process with bad
        # file descriptor errors. Note that the loggers get recreated on start
        # of the new process.
        logging.shutdown()
        close_fds()
        # Execute a new host agent program REPLACING the current process
        # NOTE: This assumes that the args passed to the new hostagent process
        # are the same as the current hostagent process. Needs more work if this
        # has to change between 2 versions of hostagent.
        os.execve(sys.argv[0], sys.argv, os.environ)

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
            # Agent update doesn't restart the hostagent process itself.
            process_agent_update(agent_info, agent_app_db, app_cache,
                                 agent_app_class, log)
            # Restart the hostagent. A new instance of the agent will take over
            # this process space after this step.
            reboot_agent()
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

    def process_support_request(upload, label, reupload=False):
        """
        Handle the request to generate the support bundle and send the file
        to the backbone master through rabbitmq broker.
        """
        _pending_support_bundle = {'upload': upload, 'label': label,
                                   'pending': True }
        if 'channel' not in state:
            log.warn('Not sending support bundle because channel is closed')
            return
        msg = {
            'opcode': 'support',
            'data': {
                'host_id': _host_id,
                'info': get_sysinfo(log),
                'upload': upload,
                'label': label,
            }
        }

        try:
            if not reupload or not os.path.exists(_support_file_location):
                datagatherer.generate_support_bundle(_support_file_location, log)
            with open(_support_file_location, 'rb') as f:
                # Choose base64 encoding to transfer binary content
                contents_str_binary = base64.b64encode(f.read())
                msg['data']['contents'] = contents_str_binary.decode()
            msg['status'] = 'success'
            msg['error_message'] = ''
        except Exception as e:
            log.exception('Support bundle generation failed.')
            msg['status'] = 'error'
            msg['error_message'] = str(e)
            msg['data']['contents'] = ''

        channel = state['channel']
        log.info('Publishing support bundle message to broker')
        try:
            channel.basic_publish(exchange=constants.BBONE_EXCHANGE,
                                  routing_key=constants.MASTER_TOPIC,
                                  body=json.dumps(msg))
        except Exception:
            if reupload:
                # If 'reupload' was set to True and we still could not publish
                # the support bundle then give up on this bundle.
                log.exception("Exception uploading support bundle second time"
                              ". Upload will not be retried.")
                _pending_support_bundle = {'pending': False}
            # Same behavior as before. This will force hostagent to
            # re-create the channel
            raise

        _pending_support_bundle = {'pending': False}

    def process_support_command(command):
        """
        Handle the request to run the support command and send the output
        to the backbone master through rabbitmq broker.
        """
        def _is_command_allowed(allowed_commands):

            for regex in allowed_commands:
                regex = re.compile(regex)
                if regex.match(command):
                    return True
            return False

        msg = {
            'opcode': 'support_command_response',
            'data': {
                'host_id': _host_id,
                'info': get_sysinfo(log),
                'command': command,
            }
        }

        try:
            data = msg['data']
            # This list is prepared each time support command is issued.
            # Presuming this is OK as running support is a special, infrequent
            # operation
            allowed_commands = load_allowed_commands()
            if _is_command_allowed(allowed_commands):
                log.info('Running command: %s' % command)
                # If the command involves the hostagent service,
                # do not capture the stdout due to issues with restarting
                if command.startswith('sudo service pf9-hostagent ') or \
                   command.startswith('sudo /etc/init.d/pf9-hostagent ') or \
                   command == 'sudo systemctl restart pf9-hostagent':
                    stdout = (None,)
                else:
                    stdout = ()
                data['rc'], data['out'], data['err'] = pf9_app_run_command(
                    command, *stdout)
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
        log.debug('--- handle_msg begin for opcode %s ---' % msg['opcode'])
        desired_config = load_desired_config(log)
        try:
            if msg['opcode'] not in ('ping', 'heartbeat', 'set_config',
                                     'set_agent', 'exit', 'get_support',
                                     'support_command', 'update_cert'):
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
            if msg['opcode'] == 'get_support':
                log.info('Received get_support message')
                process_support_request(msg['upload'], msg['label'])
                return
            if msg['opcode'] == 'support_command':
                log.info('Received support_command message: %s' % msg['command'])
                process_support_command(msg['command'])
                return
            if msg['opcode'] == 'update_cert':
                log.info('Received update_cert message.')
                # Wake-up the cert update thread to process update_cert req.
                if util.vouch_present:
                    log.debug('Sending event to Cert-Update thread to update '\
                        'host certs.')
                    util.cert_update_event.set()
                else:
                    log.info('Hostagent was not able to connect to vouch '\
                        'server. Ignoring update_cert message.')
                return
            current_config = get_current_config()
            if msg['opcode'] == 'set_agent':
                log.info('Received set_agent message')
                if desired_config is None:
                    desired_config = current_config
                update_agent(msg['data'], current_config, desired_config)
                return
            if msg['opcode'] == 'set_config':
                desired_config = msg['data']
                state['converge_attempts'] = 0
            else:
                if msg['opcode'] == 'ping':
                    log.info('Received ping message')
                if desired_config is None:
                    desired_config = current_config
            converged = valid_and_converged(current_config, desired_config)
        except (TypeError, KeyError, Pf9Exception):
            log.exception('Bad message, app config or reading current app '
                          'config. Message : %s', msg)
            return

        _handle_iaas_3166(log, disable_iaas_1366_handling, desired_config)
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

        if state['converge_attempts'] >= max_converge_attempts:
            log.info('In failed state until next set_config message...')
            send_status('failed', current_config, desired_config)
            return

        log.info('--- Converging ---')
        send_status('converging', current_config, desired_config)
        state['converge_attempts'] += 1
        if state['converge_attempts'] == max_converge_attempts:
                # This is the last convergence attempt. Generate the support
                # request and send it to the DU as part of the last
                # convergence attempt
                process_support_request(True, None)

        try:
            process_apps(app_db, app_cache, remote_app_class,
                         desired_config, log=log,
                         current_config=current_config,
                         url_interpolations=url_interpolations)
        except Pf9Exception as e:
            log.error('Exception during apps processing: %s', type(e))

        try:
            current_config = get_current_config()
        except Pf9Exception:
            log.exception('Reading current configuration failed.')
            return

        converged = valid_and_converged(current_config, desired_config)
        if converged:
            assert is_satisfied_by(desired_config, current_config)
            status = 'ok'
            # TODO: update AMQP subscriptions to include app-specific topics
            log.info('Converge succeeded')
            desired_config = None
        else:
            # TODO: increase heartbeat period when retrying, up to a limit
            if state['converge_attempts'] >= max_converge_attempts:
                log.error('Entering failed state after %d converge attempts',
                          state['converge_attempts'])
                status = 'failed'
            else:
                status = 'retrying'
            log.info('Converge failed')
        send_status(status, current_config, desired_config)

    def consume_msg(ch, method, properties, body):
        # Python3: JSON object cannot be 'bytes'. It has to be a string.
        handle_msg(json.loads(body.decode()))

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
        # Special handling for retrying a failed support bundle upload. If
        # _pending_support_bundle['pending'] is set to True it indicates
        # that support bundle could not uploaded and an exception was raised
        # in process_support_request. The exception would have caused the
        # start loop to re-initiated. This behavior is similar to behavior
        # prior to this change. If handle_msg is successful then we have a
        # functioning connection to the broker and we can retry uploading the
        # bundle. This is the second attempt and if this is unsuccessful as
        # well then _pending_support_bundle['pending'] will be reset in
        # process_support_request to prevent further retries to upload same
        # bundle.
        if _pending_support_bundle.get('pending', False):
            process_support_request(_pending_support_bundle.get('upload'),
                                    _pending_support_bundle.get('label'),
                                    reupload=True)

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
    amqp_hb_itvl = float(config.get('amqp', 'amqp_heartbeat_interval')) \
        if config.has_option('amqp', 'amqp_heartbeat_interval') else 30
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
                         amqp_heartbeat_interval=amqp_hb_itvl,
                         ssl_options=ssl_options,
                         socket_timeout=socket_timeout)  # in secs

    if 'connection_closed_unexpectedly' in state:
        log.error('Connection closed unexpectedly.')
        raise AMQPConnectionError
