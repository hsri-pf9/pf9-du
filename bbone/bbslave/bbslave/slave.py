# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

"""
Main entry point for backbone slave agent (a.k.a pf9-hostagent)
"""

__author__ = 'leb'

from pika.exceptions import AMQPConnectionError
import session
import logging, logging.handlers
from ConfigParser import ConfigParser
import time
import datetime
import errno

def reconnect_loop(config):
    """
    Continually attempts to establish connection to AMQP broker.
    :param ConfigParser config: configuration object
    """
    retry_period = int(config.get('hostagent', 'connection_retry_period'))
    # Setup logger
    log = logging.getLogger('hostagent')
    log_handler = None
    log_level_name = config.get('hostagent', 'log_level_name')
    log_format = logging.Formatter('%(asctime)s - %(filename)s'
                                   ' %(levelname)s - %(message)s')
    if config.has_option('hostagent', 'console_logging'):
        log_handler = logging.StreamHandler()
    else:
        log_rotate_count = config.getint('hostagent', 'log_rotate_max_count')
        log_file_size = config.getint('hostagent', 'log_rotate_max_size')
        log_name = config.get('hostagent', 'log_file_name')
        log_handler = logging.handlers.RotatingFileHandler(log_name,
                                                           maxBytes=log_file_size,
                                                           backupCount=log_rotate_count)

    log_handler.setLevel(getattr(logging, log_level_name))
    log_handler.setFormatter(log_format)
    log.addHandler(log_handler)
    use_mock = config.has_option('hostagent', 'USE_MOCK')
    if use_mock:
        from pf9app.mock_app_db import MockAppDb as AppDb
        from pf9app.mock_app_cache import MockAppCache as AppCache
        from pf9app.mock_app import MockRemoteApp as RemoteApp
    else:
        from pf9app.pf9_app import Pf9RemoteApp as RemoteApp
        from pf9app.pf9_app_db import Pf9AppDb as AppDb
        from pf9app.pf9_app_cache import Pf9AppCache as AppCache

    log.info('-------------------------------')
    log.info('Platform 9 host agent started at %s ', datetime.datetime.now())

    app_db = AppDb()
    app_cache = AppCache(config.get('hostagent', 'app_cache_dir'))

    while True:
        try:
            session.start(config, log, app_db, app_cache, RemoteApp)
        except AMQPConnectionError:
            log.error('Connection error. Retrying in %d seconds.', retry_period)
            time.sleep(retry_period)
        except KeyboardInterrupt:
            log.info('Terminated by user. Exiting.')
            break
        except IOError as e:
            if e.errno is errno.EINTR:
                log.info('Terminated by user. Exiting.')
                break
            log.error('IOError with errno %d', e.errno)



