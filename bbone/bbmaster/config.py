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
        'root': {'level': 'INFO', 'handlers': ['console']},
        'bbmaster': {'level': 'DEBUG', 'handlers': ['console']},
        'py.warnings': {'handlers': ['console']},
        '__force_dict__': True
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        }
    },
    'formatters': {
        'simple': {
            'format': ('%(asctime)s %(levelname)-5.5s [%(name)s]'
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
