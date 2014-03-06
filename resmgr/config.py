# Server Specific Configurations
server = {
    'port': '8083',
    'host': '0.0.0.0'
}

# Pecan Application Configurations
app = {
    'root': 'resmgr.controllers.root.RootController',
    'modules': ['resmgr'],
    'debug': True,
    'errors': {
        404: '/error/404',
        '__force_dict__': True
    }
}

logging = {
    'loggers': {
        'root': {'level': 'INFO', 'handlers': ['console']},
        'resmgr': {'level': 'DEBUG', 'handlers': ['console']},
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


resmgr ={
    'config_file': '/etc/pf9/resmgr.conf',
    'provider': 'resmgr_provider_pf9'
}
