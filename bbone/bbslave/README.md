# Backbone slave #

Processes configuration messages from the backbone master, and sends it
status messages, including periodic heartbeats.

## Configuration ##

The configuration file for the agent is currently /etc/pf9/hostagent.conf
In the future, we should make it possible to override at the command line.

## Inbound messages ##

Currently, the agent accepts two messages: 'set_config', and 'ping'.
The JSON for 'set_config' looks something like:

    {
        'opcode': 'set_config',
        'data': {
            'app_foo': {
                'version': '1.8',
                'url': 'http://www.foo.com/ostackhost-1.0.rpm',
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
            },
            'app_bar': {
                'version': '1.0',
                'url': 'http://bar-1.0.rpm',
                'running': False,
                'config': {
                    'xx': {
                        'f':1,
                        'g':2
                    },
                }
            }
        }
    }

In response to a configuration change request, the slave will install,
remove, start/stop or reconfigure pf9 applications as necessary.

The 'ping' command simply requests the slave to send a status message
immediately.

The slave always connects to the 'pf9-bbone' exchange and
receives messages published on these topics:

- 'slaves': the broadcast topic for all slaves
- '<host_id>': host / slave specific messages get published here (see discussion of 'host_id' below)
- '<pf9-appname>': every pf9 app gets its own topic. The slave listens on topics corresponding to applications currently installed.

## Outbound messages ##

The only message that the slave currently sends is 'status'.
It is sent in response to a previous 'set_config' message or
an internal heartbeat timer. This message is always sent to the 'master'
topic on the 'pf9-bbone' exchange. The JSON looks something like:

    {
        'opcode': 'status',
        'data': {
            'host_id': '00:50:56:A9:0B:BD',
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
                    'url': 'http://www.foo.com/ostackhost-1.0.rpm',
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
    }

The 'host_id' field attempts to uniquely identify the host.
The current implementation uses the MAC address of the first
alphabetically sorted network interface. A generated uuid stored
on the file system was also considered, but would break if the
host were cloned.

Current valid values for 'status' are 'ok', 'converging', and 'errors'.

