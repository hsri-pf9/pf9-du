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
        "id":"roleA",
        "name":"xxx",
        "description":"xyz"
    },
    {
        "id":"roleB",
        "name":"yyy",
        "description":"pqr"
    }
]
```
### GET /v1/roles/__id__ ###

Returns a pf9 role corresponding to id

Example:
```
{
    "id":"roleA",
    "name":"xxx",
    "description":"xyz"
}
```
### GET /v1/resources ##

Returns a dictionary of resources in the pf9 system with assigned roles

Example:
```
[
    {
        "id":"rsc_1",
        "state":"<inactive|activating|active>",
        "roles":["role_1", "role2"]
    },
    {
        "id":"rsc_2",
        "state":"<inactive|activating|active>",
        "roles":["role_2", "role5"]
    },
]
```
### GET /v1/resources/__id__ ###

Returns a descriptor for a single resource

Example:
```
{
    "id":"rsc_1",
    "info": {
        "hostname": "leb-centos-1.platform9.sys",
        "os_family": "Linux",
        "arch": "x86_64",
        "os_info": "centos 6.4 Final"
    },
    "state":"<inactive|activating|active>",
    "roles":["role4", "role3"]
}
```
### PUT /v1/resources/__id__/roles/__role_id__ ###

Activates the role specified by role_id on the resource specified by id


### DELETE /v1/resources/__id__/roles/__role_id__ ###

Removes the assigned role. Expects id of the role to remove. After removing
last role of a resource, the resource will not be used for pf9 purpose,
and reverts back to "inactive" state

