# Server Specific Configurations
server = {
    'port': '8083',
    'host': '0.0.0.0'
}

# Pecan Application Configurations
app = {
    'root': 'resmgr.controllers.root.RootController',
    'guess_content_type_from_ext': False,
    'modules': ['resmgr']
}

logging = {
    'loggers': {
        'root': {'level': 'INFO', 'handlers': ['filelogger']},
        'resmgr': {'level': 'DEBUG', 'handlers': ['filelogger'], 'propagate': False},
        'keystonemiddleware.auth_token': {'level': 'INFO', 'handlers': ['filelogger']},
        'py.warnings': {'handlers': ['filelogger']},
        '__force_dict__': True
    },
    'handlers': {
        'filelogger': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'maxBytes': 10485760,
            'backupCount': 10,
            'filename': '/var/log/pf9/resmgr.log',
            'formatter': 'simple'
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        }
    },
    'formatters': {
        'simple': {
            'format': ('%(asctime)s %(levelname)s [%(name)s]'
                       '[%(threadName)s] %(message)s')
        }
    },
    'disable_existing_loggers': False
}

resmgr ={
    'config_file': '/etc/pf9/resmgr.conf',
    'provider': 'resmgr_provider_pf9',

    # Enforce keystone RBAC policies. Optional, defaults to True.
    # May be overridden in paste ini config.
    'enforce_policy' : False
}
