# Backbone Master #

The backbone master allows querying and configuring hosts that are integrated
the pf9 infrastructure. It can query host information as well configuration of
certain apps on the host.

## Data format ##

All data is exchanged in JSON format.

## API ##

These are the REST API endpoints.

### GET /v1/hosts/ids/ ###

Returns the list of host ids that is controlled by this host management
server. Example: [ "sah8a7a", "da79das" ]

### GET /v1/hosts/<id> ###

Returns a description for the host with the provided host id.
The 'info' field contains information about the host's hardware and OS.
Valid values for 'status' are 'ok', 'converging', 'errors', and 'missing'.
The 'apps' field describes the currently installed pf9 applications and
their configuration.

Example:

    {
        'host_id': 'da79das',
        'status': 'ok',
        'info': {
            'hostname': 'leb-centos-1.platform9.sys',
            'os_family': 'Linux',
            'arch': 'x86_64',
            'os_info': 'centos 6.4 Final'
        },
        'apps': {
            'app_foo': {
                'version': '1.8',
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
    }

### GET /v1/hosts/ ###
Returns a list of all host descriptors.

### GET /v1/hosts/<id>/apps ###
Returns the apps configuration for the specified host.

### PUT /v1/hosts/<id>/apps ###
Sets the desired pf9 application configuration state of the specified host.
The expected format is similar to the 'apps' section of the descriptor returned
by GET /v1/hosts/<id> as described above.

Subsequent GETs on /v1/hosts/<id> will reflect the old configuration for a
while until the configuration is successfully applied.

If the host has not yet registered with the backbone server at the time
of the PUT, the server creates a place holding descriptor for it, sets
its 'host_id' field to the specified id, and sets 'status' to 'missing'.
The 'apps' and 'info' fields are not set.
The desired apps config is stored internally in memory. Later, if a backbone
slave reports the existence of the host, 'info' and 'apps' are updated with
information from the slave, and the desired apps configuration is sent to
the slave for convergence.



