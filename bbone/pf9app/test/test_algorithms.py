# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'leb'

from pf9app.app import App
from pf9app.algorithms import process_apps
from pf9app.mock_app_db import MockAppDb
from pf9app.mock_app_cache import MockAppCache
from pf9app.mock_app import MockRemoteApp

def test_algorithms():
    app_db = MockAppDb()
    app_cache = MockAppCache()

    # Install two apps
    new_config = {
        'foo': {
            'version': '1.0',
            'url': 'http://foo-1.0.rpm',
            'running': True,
            'config': {
                'default': {
                    'x':1,
                    'y':2
                },
                'backup': {
                    'x':3,
                    'y':4
                }
            }
        },
        'bar': {
            'version': '1.0',
            'url': 'http://bar-1.0.rpm',
            'running': True,
            'config': {
                'xx': {
                    'f':1,
                    'g':2
                },
            }
        }
    }
    changes = process_apps(app_db, app_cache, MockRemoteApp, new_config)
    assert changes == 2
    installed_apps = app_db.query_installed_apps()
    assert len(installed_apps.keys()) == 2
    assert 'bar' in installed_apps
    foo = installed_apps['foo']
    assert isinstance(foo, App)
    assert foo.name == 'foo'
    assert foo.running
    assert foo.version == '1.0'
    assert foo.get_config()['default']['x'] == 1

    # Delete bar, upgrade foo, and install ostackhost
    new_config = {
        'foo': {
            'version': '1.2',
            'url': 'http://foo-1.2.rpm',
            'running': True,
            'config': {
                'default': {
                    'x':5,
                    'y':6
                },
                'backup': {
                    'x':4,
                    'y':6
                }
            }
        },
        'ostackhost': {
            'version': '2.0',
            'url': 'http://ostackhost-2.0.rpm',
            'running': False,
            'config': {
                'yy': {
                    'c':1,
                    'v':2
                },
            }
        }
    }
    changes = process_apps(app_db, app_cache, MockRemoteApp, new_config)
    assert changes == 3
    installed_apps = app_db.query_installed_apps()
    assert len(installed_apps.keys()) == 2
    assert 'bar' not in installed_apps
    foo = installed_apps['foo']
    assert foo.version == '1.2'
    assert foo.get_config()['backup']['y'] == 6
    ostackhost = installed_apps['ostackhost']
    assert isinstance(ostackhost, App)
    assert not ostackhost.running

    # No changes
    changes = process_apps(app_db, app_cache, MockRemoteApp, new_config)
    assert changes == 0

    # Change foo's configuration
    new_config['foo']['config']['backup']['x'] = 5
    changes = process_apps(app_db, app_cache, MockRemoteApp, new_config)
    assert changes == 1
    installed_apps = app_db.query_installed_apps()
    assert len(installed_apps.keys()) == 2
    foo = installed_apps['foo']
    assert foo.get_config()['backup']['x'] == 5

    # Start ostackhost
    new_config['ostackhost']['running'] = True
    changes = process_apps(app_db, app_cache, MockRemoteApp, new_config)
    assert changes == 1
    installed_apps = app_db.query_installed_apps()
    ostackhost = installed_apps['ostackhost']
    assert ostackhost.running

    # Stop foo, apply configuration non-destructively w.r.t. ostackhost
    new_config = {'foo': new_config['foo']}
    new_config['foo']['running'] = False
    changes = process_apps(app_db, app_cache, MockRemoteApp, new_config,
                           non_destructive=True)
    assert changes == 1
    installed_apps = app_db.query_installed_apps()
    assert len(installed_apps.keys()) == 2
    assert not installed_apps['foo'].running
    assert 'ostackhost' in installed_apps

    # Uninstall everything
    new_config = {}
    changes = process_apps(app_db, app_cache, MockRemoteApp, new_config)
    assert changes == 2
    assert len(app_db.query_installed_apps().keys()) == 0


