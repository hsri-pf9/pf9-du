# Server Specific Configurations
server = {
    'port': '8082',
    'host': '0.0.0.0'
}

# Pecan Application Configurations
app = {
    'root': 'bbmaster.controllers.root.RootController',
    'modules': ['bbmaster'],
    'debug': True,
    'errors': {
        '__force_dict__': True
    }
}

# Platform 9 specific configuration

pf9 = {
    'bbone_provider': 'bbone_provider_pf9_pika'
}

logging = {
    'loggers': {
        'root': {'level': 'INFO', 'handlers': ['filelogger','filelogger2']},
        'bbmaster': {'level': 'DEBUG', 'handlers': ['filelogger','filelogger2']},
        'py.warnings': {'handlers': ['filelogger','filelogger2']},
        '__force_dict__': True
    },
    'handlers': {
        'filelogger': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'maxBytes': 2097152,
            'backupCount': 10,
            'filename': '/var/log/pf9/bbmaster.log',
            'formatter': 'simple'
        },
        'filelogger2': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'maxBytes': 2097152,
            'backupCount': 10,
            'filename': '/var/log/pf9/simple_bbmaster.log',
            'formatter': 'simple'
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
    },
    'formatters': {
        'simple': {
            'format': ('%(asctime)s %(levelname)s [%(name)s]'
                       '[%(threadName)s] %(message)s')
        }
    }
}

# Custom Configurations must be in Python dictionary format::
#
# foo = {'bar':'baz'}
#
# All configurations are accessible at::
# pecan.conf
