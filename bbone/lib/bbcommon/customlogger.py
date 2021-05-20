# Copyright (c) 2021 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'Platform9'

import logging
from logging.handlers import RotatingFileHandler
from time import gmtime

"""
This class provides configuration of logger.
It takes parameters like input logger, log file size, roation count,
log level and console logging enabled. Based on that it generates 
logging handler and registers it. If is_console is True then a stream 
handler is generated otherwise Rotation file  handler is generated.
"""

class CustomLogger:
    def __init__(self, in_logger, log_rotate_count, log_file_size, log_file_name, is_console, log_level_name="INFO"):
        self.logger = in_logger
        log_format = logging.Formatter('%(asctime)s - %(filename)s'
                                       ' %(levelname)s - %(message)s')
        if is_console == True:
            log_handler = logging.StreamHandler()
        else:
            log_handler = logging.handlers.RotatingFileHandler(log_file_name,
                                                           maxBytes=log_file_size,
                                                        backupCount=log_rotate_count)
        log_format.converter = gmtime
        log_handler.setFormatter(log_format)
        self.logger.addHandler(log_handler)
        self.level = getattr(logging, log_level_name)
        self.logger.setLevel(self.level)

    def write(self, msg):
        if msg and not msg.isspace():
            self.logger.log(self.level, msg)

    def flush(self): pass
