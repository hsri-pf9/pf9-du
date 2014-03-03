# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'leb'

from app import App, RemoteApp
from app_db import AppDb
from app_cache import AppCache
from configutils.configutils import is_dict_subset
import logging
from logging import Logger

def process_apps(app_db, app_cache, remote_app_class, new_config,
                 non_destructive=False, probe_only=False, log=logging):
    """
    Processes the transition from a current to a new application configuration.

    Removes, upgrades, installs, stops and starts pf9 applications as necessary.
    The upgrade algorithm is a bit simplistic and will be improved
    later.
    :param AppDb app_db: The database of installed applications
    :param AppCache app_cache: A cache manager for downloaded applications
    :param type remote_app_class: A class capable of creating
     a RemoteApp object from an application name and URL.
    :param dict new_config: The new application configuration, in the form
     of a JSON compatible dictionary, mapping app names to app specifications.
    :param bool non_destructive: Do not delete installed applications not
     present in the specified configuration.
    :param bool probe_only: determine if changes are needed, but don't
     actually perform the changes.
    :param Logger log: logger
    :return: the number of application changes
    :rtype: int
    """

    changes = 0
    installed_apps = app_db.query_installed_apps()
    installed_app_names = set(installed_apps.keys())
    specified_app_names = set(new_config.keys())
    deleted_app_names = installed_app_names - specified_app_names
    new_app_names = specified_app_names - installed_app_names
    identical_app_names = installed_app_names & specified_app_names
    if not non_destructive:
        for app_name in deleted_app_names:
            app = installed_apps[app_name]
            assert isinstance(app, App)
            if not probe_only:
                app.uninstall()
            changes += 1
    for app_name in identical_app_names:
        app = installed_apps[app_name]
        new_app_spec = new_config[app_name]
        assert isinstance(new_app_spec, dict)
        new_app_config = new_app_spec['config']
        if app.version != new_app_spec['version']:
            new_app = remote_app_class(name=app_name,
                                       version=new_app_spec['version'],
                                       url=new_app_spec['url'],
                                       app_db=app_db,
                                       app_cache=app_cache,
                                       log=log)
            assert isinstance(new_app, RemoteApp)
            if not probe_only:
                new_app.download()
                app.uninstall()
                new_app.install()
                assert new_app.version == new_app_spec['version']
                new_app.set_config(new_app_config)
                new_app.set_run_state(new_app_spec['running'])
            changes += 1
        elif not is_dict_subset(new_app_config, app.get_config()):
            # The app's set_config script is responsible for restarting
            # or reloading the app service after the change if app is running.
            if not probe_only:
                app.set_config(new_app_config)
            changes += 1
        elif app.running != new_app_spec['running']:
            if not probe_only:
                app.set_run_state(new_app_spec['running'])
            changes += 1
    for app_name in new_app_names:
        new_app_spec = new_config[app_name]
        new_app_config = new_app_spec['config']
        new_app = remote_app_class(name=app_name,
                                   version=new_app_spec['version'],
                                   url=new_app_spec['url'],
                                   app_db=app_db,
                                   app_cache=app_cache,
                                   log=log)
        assert isinstance(new_app, RemoteApp)
        if not probe_only:
            new_app.download()
            new_app.install()
            new_app.set_config(new_app_config)
            new_app.set_run_state(new_app_spec['running'])
        changes += 1
    return changes




