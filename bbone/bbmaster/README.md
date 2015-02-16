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

### GET /v1/hosts/__id__ ###

Returns a description for the host with the provided host id.
The 'info' field contains information about the host's hardware and OS.
Valid values for 'status' are 'ok', 'converging', 'retrying', 'failed',
and 'missing'.
The 'apps' field describes the currently installed pf9 applications and
their configuration. The 'desired_apps' field only exists for the 'converging',
'retrying' and 'failed' states, and describes the pf9 application state that
the host is attempting to converge towards.
The 'timestamp' field denotes the time when this state was processed by the
backbone master
The host_agent field describes the details of the host agent that is currently
running on that host. It reports the version of the host agent and its status.
Current possible values for status are 'running' and 'updating'.

Example:
```
    {
        'host_id': 'da79das',
        'status': 'ok',
        'timestamp': '2014-04-07 19:00:14.301721'
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
        'desired_apps': {
            ...
        }
        'host_agent': {
            'status': 'running',
            'version': '1.0.0-1'
        }
    }
```
### GET /v1/hosts/ ###
Returns a list of all host descriptors.

### POST /v1/hosts/__id__/support/bundle ###
Sends a request to the host agent on the specified host to generate and return a
support bundle to the deployment unit. The request is asynchronous and not
guaranteed to succeed.
Returns a 404 error code if the specified host does not exist.

### POST /v1/hosts/__id__/support/command ###
Sends a request to the host agent on the specified host to run a command and
return the output to the deployment unit. The request is asynchronous and not
guaranteed to succeed.
Returns a 404 error code if the specified host does not exist.

The command must be specified in the json body of the request.
Body format:
        {'command' : '<command to run>'}

The command will only be executed if it matches the list of allowed
commands:

[
   'sudo service pf9-*',
   'rm -rf /var/cache/pf9apps/*'
]

### GET /v1/hosts/__id__/apps ###
Returns the apps configuration for the specified host.

### GET /v1/hosts/__id__/apps_internal ###
Returns the apps configuration for the specified host, including internal
infrastructure applications that are normally hidden (e.g. pf9-comms)

### PUT /v1/hosts/__id__/apps ###
Sets the desired pf9 application configuration state of the specified host.
The expected format is similar to the 'apps' section of the descriptor returned
by GET /v1/hosts/__id__ as described above.

Subsequent GETs on /v1/hosts/__id__ will reflect the old configuration for a
while until the configuration is successfully applied.

If the host has not yet registered with the backbone server at the time
of the PUT, the server creates a place holding descriptor for it, sets
its 'host_id' field to the specified id, and sets 'status' to 'missing'.
The 'apps' and 'info' fields are not set.
The desired apps config is stored internally in memory. Later, if a backbone
slave reports the existence of the host, 'info' and 'apps' are updated with
information from the slave, and the desired apps configuration is sent to
the slave for convergence.

Setting a desired configuration state may have the secondary side effect of
installing or upgrading infrastructure software used internally by the backbone
system on the host, such as the pf9-comms application.

### GET /v1/hosts/__id__/hostagent ###
Returns information about the host agent that is present on the specified
host. Response contains the status of the agent and the version of the
host agent that it is currently running.
```
    {
        'status': 'running',
        'version': '1.0.0-1'
    }
```

### PUT /v1/hosts/__id__/hostagent ###
Update the hostagent on the host specified by the host id. The request body
should provide the a URL for the hostagent rpm that needs to be installed on
the host.
Request body:
```
    {
        'name': 'pf9-hostagent',
        'version': '1.2.3',
        'url': 'http://agentserver/hostagent/pf9-hostagent-1.2.3.x86-64.rpm'
    }
```

