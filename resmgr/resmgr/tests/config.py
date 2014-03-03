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

# Custom Configurations must be in Python dictionary format::
#
# foo = {'bar':'baz'}
#
# All configurations are accessible at::
# pecan.conf
