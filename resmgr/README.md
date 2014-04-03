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
        "description": "Simple role A"
    },
    {
        "name": "roleB",
        "display_name": "Role B",
        "description": "Another role B"
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
    "description": "Simple role A"
}
```
### GET /v1/hosts ##

Returns a dictionary of hosts in the pf9 system with assigned roles

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
            "os_info": "centos 6.4 Final"
        },
        "roles": ["role_1", "role2"]
    },
    {
        "id": "rsc_2",
        "state": "<inactive|activating|active>",
        "info": {
            "hostname": "leb-centos-1.platform9.sys",
            "os_family": "Linux",
            "arch": "x86_64",
            "os_info": "centos 6.4 Final"
        },
        "roles": ["role_2", "role5"]
    },
]
```
### GET /v1/hosts/__id__ ###

Returns a descriptor for a single host

Example:
```
{
    "id": "rsc_1",
    "info": {
        "hostname": "leb-centos-1.platform9.sys",
        "os_family": "Linux",
        "arch": "x86_64",
        "os_info": "centos 6.4 Final"
    },
    "state": "<inactive|activating|active>",
    "roles": ["role4", "role3"]
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

Activates the role specified by role_name on the host specified by id


### DELETE /v1/hosts/__id__/roles/__role_name__ ###

Removes the assigned role. Expects name of the role to remove. After removing
last role of a host, the host will not be used for pf9 purpose,
and reverts back to "inactive" state

