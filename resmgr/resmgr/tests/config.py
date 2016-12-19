import os

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
        '404': '/error/404',
        '__force_dict__': True
    }
}

logging = {
    'loggers': {
        'root': {'level': 'INFO', 'handlers': ['console']},
        'resmgr': {'level': 'DEBUG', 'handlers': ['console']},
        'keystonemiddleware.auth_token': {'level': 'DEBUG', 'handlers': ['console']},
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

resmgr = {
    'config_file': os.path.join(os.getcwd(), 'resmgr/tests/resmgr.conf'),
    'provider': 'resmgr_provider_mem',

    # Enforce keystone RBAC policies. Optional, defaults to True.
    # Must be false for non-auth tests to run. Auth tests override this
    # when they load the paste'd version of the app.
    'enforce_policy' : False
}

