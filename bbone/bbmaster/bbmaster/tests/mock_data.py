# Mock data to service the mock implementation of the provider interface
data = {
    '2d734f3a-8a16-11e3-909d-005056a93468': {
        'host_id': '2d734f3a-8a16-11e3-909d-005056a93468',
        'status': 'ok',
        'timestamp': '2014-04-07 19:00:14.301721',
        'info': {
            'hostname':'foo.acme.com',
            'os_family': 'Linux',
            'arch': 'x86_64',
            'os_info': 'centos 6.4 Final'
        },
        'apps': {
            'service1' : {
                'version': '1.1',
                'running': True,
                'config': {
                    'default': {
                        'x':3,
                        'y':2
                    },
                    'backup': {
                        'x':3,
                        'y':5
                    }
                }
            }
        },
    },
    '468860b4-8a16-11e3-909d-005056a93468': {
        'host_id': '468860b4-8a16-11e3-909d-005056a93468',
        'status': 'ok',
        'timestamp': '2014-04-07 19:00:14.301721',
        'info': {
            'hostname':'bar.acme.com',
            'os_family': 'Linux',
            'arch': 'x86_64',
            'os_info': 'Ubuntu Server 12.04'
        },
        'apps': {
            'service1' : {
                'version': '1.0',
                'running': True,
                'config': {
                    'x': 100,
                    'y': 102
                }
            },
            'service2' : {
                'version': '2.0',
                'running': False,
                'config': {
                    'z': 300,
                    'w': 308
                }
            }
        },
    }
}
