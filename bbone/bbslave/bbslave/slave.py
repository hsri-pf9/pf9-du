# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

"""
Main entry point for backbone slave agent (a.k.a pf9-hostagent)
"""

__author__ = 'leb'

import sys
from pika.exceptions import AMQPConnectionError
from bbslave.session import start
import logging, logging.handlers
from six.moves.configparser import ConfigParser
import time
import datetime
import errno
from bbcommon.utils import get_ssl_options
from bbcommon.customlogger import CustomLogger
import threading
from bbslave.cert_update_thread import cert_update_thread
from bbslave.package_cleaner import clean_packages
from bbslave.sysinfo import get_cpu_info

"""
This function sets up the logging for given parameters.
If is_daemon parameter is True then it redirects the stdout and
stderr to the logger.
"""
def setup_log(is_daemon, log_name, log_file_size, 
                     log_rotate_count, log_level_name, console_logging):
    if is_daemon == True:
        clog = logging.getLogger('STDOUT')
    else:
        clog = logging.getLogger('hostagent')

    if not clog.handlers:       
        custom_logger = CustomLogger(clog, log_rotate_count, log_file_size,
                                     log_name, console_logging,  log_level_name)
        if is_daemon == True:
            sys.stdout = custom_logger
            sys.stderr = custom_logger

"""
This function reads the configuration and generates python logger
by calling setup_log function for hostagent-daemon and hostagent
"""
def setup_service_logging(config):

    # Setup logger
    log = logging.getLogger('hostagent')

    if not log.handlers:
        log_level_name = config.get('hostagent', 'log_level_name')
        log_name = ''
        log_rotate_count = 0
        log_file_size = 0
        console_logging = False
        if config.has_option('hostagent', 'console_logging'):
            console_logging = True
        else:
            log_rotate_count = config.getint('hostagent', 'log_rotate_max_count')
            log_file_size = config.getint('hostagent', 'log_rotate_max_size')
            log_name = config.get('hostagent', 'log_file_name')
            daemon_file_name = "/var/log/pf9/hostagent-daemon.log"
            setup_log(True, daemon_file_name, log_file_size, log_rotate_count,
                             log_level_name, False)
        setup_log(False, log_name, log_file_size, log_rotate_count,
                             log_level_name, console_logging)

def reconnect_loop(config):
    """
    Continually attempts to establish connection to AMQP broker.
    :param ConfigParser config: configuration object
    """
    retry_period = int(config.get('hostagent', 'connection_retry_period'))
    # Setup logger
    setup_service_logging(config)
    log = logging.getLogger('hostagent')
    use_mock = config.has_option('hostagent', 'USE_MOCK')
    if use_mock:
        # dynamically import class from the config file
        if config.has_option('hostagent', 'mock_app_class'):
            mock_app_class = config.get('hostagent', 'mock_app_class')
            loaded_module = __import__('pf9app.mock_app', fromlist=[mock_app_class])
            RemoteApp = getattr(loaded_module, mock_app_class)
        else:
            from pf9app.mock_app import MockRemoteApp as RemoteApp

        from pf9app.mock_app_db import MockAppDb as AppDb
        from pf9app.mock_app_cache import MockAppCache as AppCache
        # TODO: Figure out if we need a mock implementation for agentAppDb
        Pf9AgentDb = AppDb
        Pf9AgentApp = RemoteApp
    else:
        from pf9app.pf9_app import Pf9RemoteApp as RemoteApp
        from pf9app.pf9_app import Pf9AgentApp
        from pf9app.pf9_app_db import Pf9AppDb as AppDb, Pf9AgentDb
        from pf9app.pf9_app_cache import Pf9AppCache as AppCache
    # Clean up old packages
    if config.has_option('hostagent', 'skip_pf9app_cache_cleanup') == False or config.get('hostagent', 'skip_pf9app_cache_cleanup') == False:
        clean_packages(log)
    # Log cpu info
    log.info('Cpu info: %s' % get_cpu_info(log))
    # Start the cert update thread.
    cert_thread = threading.Thread(
            name='Cert-Update-Thread',
            target=cert_update_thread,
            args=(config, log))
    log.info('Starting the cert update thread.')
    cert_thread.start()

    log.info('-------------------------------')
    log.info('Platform9 host agent started at %s on thread %s',
             datetime.datetime.now(), threading.current_thread().ident)

    app_db = AppDb(log)
    agent_app_db = Pf9AgentDb(log)
    ssl_options = get_ssl_options(config)
    app_cache_kwargs = ssl_options if ssl_options else {}
    app_cache_kwargs['cachelocation'] = config.get('hostagent', 'app_cache_dir')
    app_cache_kwargs['log'] = log
    app_cache = AppCache(**app_cache_kwargs)

    while True:
        try:
            start(config, log, app_db, agent_app_db, app_cache,
                          RemoteApp, Pf9AgentApp,
                          channel_retry_period=retry_period)
            # Clean exit
            return
        except AMQPConnectionError:
            log.exception('Connection error. Retrying in %d seconds.', retry_period)
            time.sleep(retry_period)
        except KeyboardInterrupt:
            log.info('Terminated by user. Exiting.')
            break
        except IOError as e:
            if e.errno is errno.EINTR:
                log.info('Terminated by user. Exiting.')
                break
            log.exception('IOError: %s', e)
        except Exception:
            # A catch all clause to avoid the slave going down in case of
            # unexpected exceptions. Log and continue
            log.exception('Unexpected error')

            # Sleep a while to avoid spinning and filling up the log file
            time.sleep(retry_period)


