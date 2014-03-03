# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

"""
Test data to run the slave tests
"""

test_data_install = [
    {
        'opcode': 'set_config',
        'expect_converging': True,
        'desired_config': {
            # Introduce 1 app
            'foo': {
                'version': '1.0',
                'url': 'http://zz.com/foo-1.0.rpm',
                'running': True,
                'config': {
                    'default': {
                        'x':1,
                        'y':2
                    },
                    'backup': {
                        'x':3,
                        'y':5
                    }
                }
            }
        }
    },
    {
        'opcode': 'set_config',
        'expect_converging': True,
        'desired_config': {
            # Introduce 2nd app bar, change foo version
            'foo': {
                'version': '1.5',
                'url': 'http://zz.com/foo-1.0.rpm',
                'running': True,
                'config': {
                    'default': {
                        'x':1,
                        'y':2
                    },
                    'backup': {
                        'x':3,
                        'y':5
                    }
                }
            },
            'bar': {
                'version': '1.0',
                'url': 'http://xx.com/bar-1.0.rpm',
                'running': False,
                'config': {
                    'xx': {
                        'f':1,
                        'g':2
                    },
                    }
            }
        }
    },
    {
        'opcode': 'set_config',
        'expect_converging': True,
        'desired_config': {
            # Remove foo, Add ostackhost
            'ostackhost': {
                'version': '1.8',
                'url': 'http://www.foo.com/ostackhost-1.8.rpm',
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
            'bar': {
                'version': '1.0',
                'url': 'http://xx.com/bar-1.0.rpm',
                'running': False,
                'config': {
                    'xx': {
                        'f':1,
                        'g':2
                    },
                    }
            }
        }
    },
    {
        'opcode': 'set_config',
        'expect_converging': True,
        'desired_config': {
            # Remove bar
            'ostackhost': {
                'version': '1.8',
                'url': 'http://www.foo.com/ostackhost-1.8.rpm',
                'running': False,
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
        }
    },
    {
        'opcode': 'set_config',
        'expect_converging': True,
        'desired_config': {
            # Remove everything
        }
    }
]

test_data_config = [
    {
        'opcode': 'set_config',
        'expect_converging': True,
        'desired_config': {
            # Introduce 1 app
            'foo': {
                'version': '1.0',
                'url': 'http://zz.com/foo-1.0.rpm',
                'running': True,
                'config': {
                    'default': {
                        'x':1,
                        'y':2
                    },
                    'backup': {
                        'x':3,
                        'y':5
                    }
                }
            }
        }
    },
    {
        'opcode': 'set_config',
        'expect_converging': True,
        'desired_config': {
            # Change run state
            'foo': {
                'version': '1.0',
                'url': 'http://zz.com/foo-1.0.rpm',
                'running': False,
                'config': {
                    'default': {
                        'x':1,
                        'y':2
                    },
                    'backup': {
                        'x':3,
                        'y':5
                    }
                }
            }
        }
    },
    {
        'opcode': 'set_config',
        'expect_converging': True,
        'desired_config': {
            # Change version.
            'foo': {
                'version': '2.0',
                'url': 'http://zz.com/foo-1.0.rpm',
                'running': False,
                'config': {
                    'default': {
                        'x':1,
                        'y':2
                    },
                    'backup': {
                        'x':3,
                        'y':5
                    }
                }
            }
        }
    },
    {
        'opcode': 'set_config',
        'expect_converging': False,
        'desired_config': {
            # No change in any setting
            'foo': {
                'version': '2.0',
                'url': 'http://zz.com/foo-1.0.rpm',
                'running': False,
                'config': {
                    'default': {
                        'x':1,
                        'y':2
                    },
                    'backup': {
                        'x':3,
                        'y':5
                    }
                }
            }
        }
    },
    {
        'opcode': 'set_config',
        'expect_converging': True,
        'desired_config': {
            # Change config
            'foo': {
                'version': '2.0',
                'url': 'http://zz.com/foo-1.0.rpm',
                'running': False,
                'config': {
                    'default': {
                        'x':11,
                        'y':12
                    },
                    'backup': {
                        'x':13,
                        'y':15
                    }
                }
            }
        }
    },
    {
        'opcode': 'set_config',
        'expect_converging': True,
        'desired_config': {
            # Change everything, including version
            'foo': {
                'version': '3.0',
                'url': 'http://zz.com/foo-1.0.rpm',
                'running': True,
                'config': {
                    'default': {
                        'x':31,
                        'y':32
                    },
                    'backup': {
                        'x':33,
                        'y':35
                    }
                }
            }
        }
    },
    {
        'opcode': 'set_config',
        'expect_converging': True,
        'desired_config': {
            # Remove everything
        }
    }
]

test_data_ping = [
    {   # Introduce 1 app
        'opcode': 'set_config',
        'expect_converging': True,
        'desired_config': {
            'foo': {
                'version': '1.0',
                'url': 'http://zz.com/foo-1.0.rpm',
                'running': True,
                'config': {
                    'default': {
                        'x':1,
                        'y':2
                    },
                    'backup': {
                        'x':3,
                        'y':5
                    }
                }
            }
        }
    },
    {   # Just ping
        'opcode': 'ping',
        'expect_converging': False,
        'desired_config': {
            'foo': {
                'version': '1.0',
                'url': 'http://zz.com/foo-1.0.rpm',
                'running': True,
                'config': {
                    'default': {
                        'x':1,
                        'y':2
                    },
                    'backup': {
                        'x':3,
                        'y':5
                    }
                }
            }
        }
    },
    {   # Just heartbeat
        'opcode': 'heartbeat',
        'expect_converging': False,
        'desired_config': {
            'foo': {
                'version': '1.0',
                'url': 'http://zz.com/foo-1.0.rpm',
                'running': True,
                'config': {
                    'default': {
                        'x':1,
                        'y':2
                    },
                    'backup': {
                        'x':3,
                        'y':5
                    }
                }
            }
        }
    },
    {
        'opcode': 'set_config',
        'expect_converging': True,
        'desired_config': {
            # Remove everything
        }
    }
]

"""
# This is a failing case. Validate first if it is an actual usecase
    {   # Change everything, except for version
        'expect_converging': True,
        'foo': {
            'version': '2.0',
            'url': 'http://zz.com/foo-1.0.rpm',
            'running': True,
            'config': {
                'default': {
                    'x':21,
                    'y':22
                },
                'backup': {
                    'x':23,
                    'y':25
                }
            }
        }
    },"""

