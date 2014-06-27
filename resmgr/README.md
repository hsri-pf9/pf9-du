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
        "active_version": "3.0.9-1"
    },
    {
        "name": "roleB",
        "display_name": "Role B",
        "description": "Another role B",
        "active_version": "1.0.2-5"
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
}
```

### PUT /v1/roles/__role_name__ ###

Sets a particular version of a role as the active version of the role. The version
of the role that is to be marked active is passed in the body of the request

Example:
```
{
    'active_version': '1.0.2-2'
}
```

On setting a role version as active, new hosts where the role is applied will install
this version of the role. However, existing hosts will continue to use the pre-existing
version of the role. To move these hosts to this active version of the role, the role
should be reapplied to these hosts.

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
        "state": "<inactive|activating|active>",
        "info": {
            "hostname": "leb-centos-1.platform9.sys",
            "os_family": "Linux",
            "arch": "x86_64",
            "os_info": "centos 6.4 Final",
            "responding": <true|false>,
            "last_response_time": <date|null>
        },
        "roles": ["role_1", "role2"],
        "role_status": "<ok|converging|retrying|failed>"
    },
    {
        "id": "rsc_2",
        "state": "<inactive|activating|active>",
        "info": {
            "hostname": "leb-centos-1.platform9.sys",
            "os_family": "Linux",
            "arch": "x86_64",
            "os_info": "centos 6.4 Final"
            "responding": <true|false>,
            "last_response_time": <date|null>

        },
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
    "state": "<inactive|activating|active>",
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

### DELETE /v1/hosts/__id__/roles/__role_name__ ###

Removes the assigned role. Expects name of the role to remove. After removing
last role of a host, the host will not be used for pf9 purpose,
and reverts back to "inactive" state

