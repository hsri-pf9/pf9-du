# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'leb'

from pf9app.app import App, RemoteApp
from pf9app.app_db import AppDb
from pf9app.app_cache import AppCache
from configutils.configutils import is_dict_subset
import logging
from logging import Logger
from pf9app.exceptions import InvalidSupportedDistro, UrlNotSpecified
import platform
from pf9app.pf9_app_cache import get_supported_distro

def process_apps(app_db, app_cache, remote_app_class, new_config,
                 non_destructive=False, probe_only=False, log=logging,
                 current_config=None,
                 url_interpolations=None):
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
    :param dict current_config: optional current application/service state.
     if not specified, the function will obtain the current state from the appdb
    :param dict url_interpolations: An optional dictionary containing
     string substitutions for the url property of a pf9 application
    :return: the number of application changes
    :rtype: int
    """

    changes = 0
    if current_config is None:
        current_config = app_db.get_current_config()
    installed_app_names = set(current_config.keys())
    installed_apps = {}
    for installed_app_name in installed_app_names:
        installed_apps[installed_app_name] = app_db.make_app(
            installed_app_name,
            current_config[installed_app_name]['version']
        )
    specified_app_names = set(new_config.keys())
    deleted_app_names = installed_app_names - specified_app_names
    new_app_names = specified_app_names - installed_app_names
    identical_app_names = installed_app_names & specified_app_names

    new_app_names = get_app_ordering(new_app_names, new_config, log)
    identical_app_names = get_app_ordering(identical_app_names, new_config, log)

    if not non_destructive:
        for app_name in deleted_app_names:
            app = installed_apps[app_name]
            assert isinstance(app, App)
            if not probe_only:
                app.uninstall()
            changes += 1

    def get_os_name():
        supported_distro = get_supported_distro(log)
        version = platform.linux_distribution()[1].lower()
        if supported_distro == 'redhat':
            if version.startswith('7'):
                return 'el7'
            if not version.startswith('6'):
                log.warn('Could not detect OS name. Defaulting to el6.')
            return 'el6'
        elif supported_distro == 'debian':
            if 'jessie' in version or version.startswith('14'):
                return 'trusty'
            if 'wheezy' not in version and not version.startswith('12'):
                log.warn('Could not detect OS name. Defaulting to precise.')
            return 'precise'
        # This code should not be reached if it is kept in sync
        # with get_supported_distro
        raise InvalidSupportedDistro('Unexpected supported distro: %s'
                                     % supported_distro)

    def url_from_app_spec(spec):
        """
        Return the url from the app spec and a boolean that indicates
        whether the url extension needs to be changed.
        """
        if 'pkginfo' in spec:
            baseurl = spec['pkginfo']['baseurl']
            filename = spec['pkginfo']['filenames_by_os'][get_os_name()]
            url = ''.join([baseurl, filename])
            change_extension = False
        elif 'url' in spec:
            url = spec['url']
            change_extension = True
        else:
            raise UrlNotSpecified

        if url_interpolations:
            url %= url_interpolations
        return url, change_extension

    for app_name in identical_app_names:
        app = installed_apps[app_name]
        new_app_spec = new_config[app_name]
        services = new_app_spec.get('service_states')
        assert isinstance(new_app_spec, dict)
        new_app_config = new_app_spec['config']
        if app.version != new_app_spec['version']:
            if not probe_only:
                url, change_extension = url_from_app_spec(new_app_spec)
                new_app = remote_app_class(name=app_name,
                                           version=new_app_spec['version'],
                                           url=url,
                                           change_extension=change_extension,
                                           app_db=app_db,
                                           app_cache=app_cache,
                                           log=log)
                assert isinstance(new_app, RemoteApp)
                new_app.download()
                app.uninstall()
                new_app.install()
                # It is possible for the actual version to differ from expected
                # if, for example, the wrong package URL was specified.
                # assert new_app.version == new_app_spec['version']
                new_app.set_config(new_app_config)
                if services is None:
                    services = { app_name : new_app_spec['running'] }
                new_app.set_desired_service_states(services)
            changes += 1
        else:
            if not is_dict_subset(new_app_config,
                                  current_config[app_name]['config']):
                # The app's set_config script is responsible for restarting
                # or reloading the app service after the change if app is running.
                if not probe_only:
                    app.set_config(new_app_config)
                changes += 1
            if services is None:
                services = { app_name : new_app_spec['running'] }
            current_services = current_config[app_name]['service_states'] if \
                'service_states' in current_config[app_name] else \
                {app_name: current_config[app_name]['running']}
            if current_services != services:
                if not probe_only:
                    app.set_desired_service_states(services)
                changes += 1
    for app_name in new_app_names:
        if not probe_only:
            new_app_spec = new_config[app_name]
            new_app_config = new_app_spec['config']
            services = new_app_spec.get('service_states')
            url, change_extension = url_from_app_spec(new_app_spec)
            new_app = remote_app_class(name=app_name,
                                       version=new_app_spec['version'],
                                       url=url,
                                       change_extension=change_extension,
                                       app_db=app_db,
                                       app_cache=app_cache,
                                       log=log)
            assert isinstance(new_app, RemoteApp)
            new_app.download()
            new_app.install()
            new_app.set_config(new_app_config)
            if services is None:
                services = { app_name : new_app_spec['running'] }
            new_app.set_desired_service_states(services)
        changes += 1
    return changes

def process_agent_update(agent_config, app_db, app_cache, agent_app_class, log):
    """
    Process update of the host agent to a new version
    :param dict agent_config: agent configuration that needs to be applied
    :param AppDb app_db: Database of agent applications
    :param AppCache app_cache: A cache manager for downloaded applications
    :param type agent_app_class: Class for the agent App class
    :param Logger log: log object
    """

    # Check the current version of the agent. Do nothing if same
    current_agent = app_db.query_installed_agent()
    if current_agent['version'] == agent_config['version']:
        log.info('pf9 agent is already at the expected version, %s',
                 agent_config['version'])
        return

    # Create an agent app object
    # Download the agent into the cache
    # Run an update on the agent
    new_agent = agent_app_class(name=agent_config['name'],
                                version=agent_config['version'],
                                url=agent_config['url'],
                                change_extension=True,
                                app_db=app_db,
                                app_cache=app_cache,
                                log=log)
    new_agent.download()
    new_agent.update()


def get_app_ordering(apps_to_order, app_config, log):
    """
    Given a list of apps to order and the config dict, return an ordered list
    of apps based on the app ranks
    """
    return sorted(apps_to_order, key=lambda t:
                                 float(app_config[t].get('rank', 0.0)))

