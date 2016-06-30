# Resource Manager #

The resource manager is source of truth for
- Hosts allocated to pf9
- Their roles in pf9 system
- (Optionally) which hosts are approved by user for specific role in pf9

## Data format ##

All data is exchanged in JSON format


## API ##

### GET /v1/roles ###

Returns a dictionary of pf9 roles available in the system

Example:
```
[
    {
        "name": "roleA",
        "display_name": "Role A",
        "description": "Simple role A",
        "active_version": "3.0.9-1",
        "default_settings": {
            "setting_name": "setting_value"
        },
    },
    {
        "name": "roleB",
        "display_name": "Role B",
        "description": "Another role B",
        "active_version": "1.0.2-5",
        "default_settings": {
            "setting_name": "setting_value"
        },
    }
]
```
### GET /v1/roles/__role_name__ ###

Returns a pf9 role corresponding to __role_name__

Example:
```
{
    "name": "roleA",
    "display_name": "Role A",
    "description": "Simple role A",
    "active_version": "3.0.9-1"
    "default_settings": {
        "setting_name": "setting_value"
    }
}
```

### GET /v1/roles/__role_name__/apps/versions ###

Returns the apps and versions of the specified __role_name__

Example:
```
{
    "app_name_1": "app_version_1",
    "app_name_2": "app_version_2"
}
```

### GET /v1/hosts ##

Returns a dictionary of hosts in the pf9 system with assigned roles.

The `last_response_time` values are used when the host is not responding.
Otherwise, this value may be null.

For unauthorized hosts, `responding`, `last_response_time`, and `role_status`
are not exposed.

Example:
```
[
    {
        "id": "rsc_1",
        "info": {
            "hostname": "leb-centos-1.platform9.sys",
            "os_family": "Linux",
            "arch": "x86_64",
            "os_info": "centos 6.4 Final",
            "responding": <true|false>,
            "last_response_time": <date|null>
        },
        "hypervisor_info": {
            "hypervisor_type": "kvm|vmwareCluster",
            "hypervisor_details": <Messages from hypervisor>
            }
        "extensions": {
            "extension 1": {
               "status": "OK|error",
               "data": <extension data>
               },
               ...
            }
        "roles": ["role_1", "role2"],
        "role_status": "<ok|converging|retrying|failed>"
    },
    {
        "id": "rsc_2",
        "info": {
            "hostname": "leb-centos-1.platform9.sys",
            "os_family": "Linux",
            "arch": "x86_64",
            "os_info": "centos 6.4 Final"
            "responding": <true|false>,
            "last_response_time": <date|null>
        },
        "hypervisor_info": {
            "hypervisor_type": "kvm|vmwareCluster",
            "hypervisor_details": <Messages from hypervisor>
            }
        "extensions": {
            "extension 1": {
               "status": "OK|error",
               "data": <extension data>
               },
               ...
            }
        "roles": ["role_2", "role5"],
        "role_status": "<ok|converging|retrying|failed>"
    },
]
```
### GET /v1/hosts/__id__ ###

Returns a descriptor for a single host.

The `last_response_time` value is used when the host is not responding.
Otherwise, this value may be null.

For unauthorized hosts, `responding`, `last_response_time`, and `role_status`
are not exposed.

Example:
```
{
    "id": "rsc_1",
    "info": {
        "hostname": "leb-centos-1.platform9.sys",
        "os_family": "Linux",
        "arch": "x86_64",
        "os_info": "centos 6.4 Final"
        "responding": <true|false>,
        "last_response_time": <date|null>
    },
    "hypervisor_info": {
            "hypervisor_type": "kvm|vmwareCluster",
            "hypervisor_details": <Messages from hypervisor>
            }
    "extensions": {
        "extension 1": {
           "status": "OK|error",
           "data": <extension data>
           },
           ...
        }
    "roles": ["role4", "role3"],
    "role_status": "<ok|converging|retrying|failed>"
}
```

### DELETE /v1/hosts/__id__ ###

Deletes the state of a host. This request is valid only for hosts that have
at least one assigned role or in the active state. As part of the deletion,
all assigned roles will be removed from the host. If the host is currently
inactive, then this request is a no-op.

Once an active host is deleted, subsequent discovery of this host will mark it
in the inactive state.

### POST /v1/hosts/__id__/support/bundle ###

Sends a request to the host agent on the specified host to generate and return a
support bundle to the deployment unit. The request is asynchronous and not
guaranteed to succeed.
Returns a 404 error code if the specified host does not exist.

### POST /v1/hosts/__id__/support/command ###

Sends a request to the host agent on the specified host to run a command
and return the output to the deployment unit. The request is asynchronous and not
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

### PUT /v1/hosts/__id__/roles/__role_name__ ###

Activates the role specified by role_name on the host specified by id. There are 3 possible
outcomes of this operation
1. If the role was not present on the host, then the role will be installed and configured
on the host
2. If the role was already present on the host and the version of the role on the host
is same as the active version of the role, no action is performed on the host
3. If the role was already present on the host but the version of the role on the host
is not the same as the active version of the role, the role on the host is updated to the
active version of the role.

The body of the request must be either empty, or a Json dictionary. A request with an
empty body is equivalent to a request with an empty Json dictionary. The dictionary specified
by the body must provide a subset of the custom settings.
Here is how the specified Json dictionary is processed.

1. The host will use the custom values specified by the dictionary.
   This will overwrite an existing custom value if it is specified in the body.
2. If the host is being upgraded and if a custom setting was not specified by the body,
   the host will keep the value it had for that custom setting before the call.
3. If this is the first time applying the role to the host and if a custom setting was not
   specified by the body, then the host will get the default value for that custom setting.


Dictionary for pf9-ostackhost:
```
{
    "instances_path": "</custom/instances/path/>"
}
```

Dictionary for pf9-imagelibrary:
```
{
    "data_directory": "</custom/imglib/directory/>"
}
```

Defaults for pf9-ostackhost:
```
instances_path = /opt/pf9/data/instances
```

Defaults for pf9-imagelibrary:
```
data_directory = /var/opt/pf9/imagelibrary/data/
```

### DELETE /v1/hosts/__id__/roles/__role_name__ ###

Removes the assigned role. Expects name of the role to remove. After removing
last role of a host, the host will not be used for pf9 purpose,
and reverts back to "inactive" state


### GET /v1/hosts/__id__/roles/__role_name__ ###
Returns a json dict with the host's custom role settings.
Returns an error code if the host does not exist or if the host does not have
the specified role

