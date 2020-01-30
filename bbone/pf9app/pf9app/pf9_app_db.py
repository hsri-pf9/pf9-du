# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'Platform9'

import errno
import logging
import os
import platform
import subprocess
import time
from six import iteritems

from pf9app.app_db import AppDb
from pf9app.pf9_app_cache import get_supported_distro
from pf9app.pf9_app import Pf9App, _run_command_with_custom_pythonpath
from pf9app.exceptions import NotInstalled, UpdateOperationFailed, \
    RemoveOperationFailed, InstallOperationFailed, Pf9Exception

if get_supported_distro() == 'debian':
    import apt
    import apt.debfile


class AptPkgMgr(object):
    """Class that interacts with APT"""

    def __init__(self, log = logging):
        self.log = log
        self.apt_rootwrap_path = '/opt/pf9/hostagent/bin/pf9-apt'
        # To install packages noninteractively, we change the environment
        # variables. There may be additional steps needed in the pf9app
        # post-install scripts to take this into account.
        os.environ.update(DEBIAN_FRONTEND='noninteractive')
        self.cache = apt.cache.Cache()

    def query_pf9_apps(self):
        """
        Query the installed packages on the machine that are pf9 apps. Packages
        that provide "pf9app" are considered as pf9 apps

        :return: dict of pf9 apps mapped to its details (name, version)
        :rtype: dict
        """
        self.log.debug('-- query_pf9_apps begin --')
        self.cache.open()
        out = {}
        items = 0
        pkgs = 0
        for pkg in self.cache.get_providing_packages('pf9app'):
            pkgs += 1
            for version in pkg.versions:
                items += 1
                out[pkg.name] = {
                    'name' : pkg.name,
                    'version' : version.source_version
                }
        self.log.debug('-- query_pf9_apps end with %d pkgs and %d items --' %
                       (pkgs, items))
        return out

    def query_pf9_agent(self):
        """
        Query the installed pf9 host agent details from the YUM repo
        :return: dictionary of agent name and version
        :rtype: dict
        """
        self.cache.open()
        pkg = self.cache["pf9-hostagent"]
        versions = pkg.versions
        # Returns the first hostagent version for now
        return {
            'name': pkg.name,
            'version': versions[0].source_version
        }

    def remove_package(self, appname):
        """
        Removes an installed app.
        :param appname: Name of  the app to remove
        :raises NotInstalled: if the app is not found/installed
        :raises RemoveOperationFailed: if the remove operation failed.
        """
        self.cache.open()
        if not self.cache.has_key(appname):
            raise NotInstalled()
        erase_cmd = 'sudo %s erase %s' % (self.apt_rootwrap_path, appname)
        code, out, err = _run_command_with_custom_pythonpath(erase_cmd)
        if code:
            self.log.error('Erase command failed : %s. Return code: %d, '
                           'stdout: %s, stderr: %s', erase_cmd, code, out, err)
            raise RemoveOperationFailed()


    def install_from_file(self, pkg_path):
        """
        Installs an app from the specified local path
        :param pkg_path: path to the package to be installed
        :raises InstallOperationFailed: if the install operation failed
        """
        install_cmd = 'sudo %s install %s' % (self.apt_rootwrap_path, pkg_path)
        code, out, err = _run_command_with_custom_pythonpath(install_cmd)
        if code:
            self.log.error('Install command failed: %s. Return code: %d, '
                           'stdout: %s, stderr: %s', install_cmd, code, out, err)
            raise InstallOperationFailed()

    def update_from_file(self, pkg_path):
        """
        Updates a package from the specified local path.
        Deb packages use the same command to install or upgrade a package, so
        this follows the same code path as an installation.
        :param str pkg_path: local path to the package to be upgraded
        :raises IntallOperationFailed: if the update operation failed.
        """
        self.install_from_file(pkg_path)


class YumPkgMgr(object):
    """Class that interacts with the YUM package manager"""

    # TODO: Consider building a package manager interface to denote all the methods
    # that need to be implemented as part of the package manager.

    def __init__(self, log = logging):
        self.log = log
        self.yum_rootwrap_path = '/opt/pf9/hostagent/bin/pf9-yum'
        # Dummy time string to insert in rpm commands
        dummy_time = time.time()
        self.dummy_time_str = str(dummy_time)

    def query_pf9_apps(self):
        """
        Query the installed packages on the machine that are pf9 apps. Packages
        that provide "pf9app" are considered as pf9 apps

        :return: dict of pf9 apps mapped to its details (name, version)
        :rtype: dict
        """
        out = {}

        query_cmd = "rpm -q --whatprovides pf9app --queryformat '%{NAME}" + self.dummy_time_str + "%{VERSION}-%{RELEASE}\n'"
        code, response, err = _run_command_with_custom_pythonpath(query_cmd)
        if code:
            self.log.error('RPM query command failed : %s. Return code: %d, '
                           'stdout: %s, stderr: %s', query_cmd, code, response, err)
            # Return empty dict in case of error.
            return out

        for line in response.splitlines():
            name, version = line.split(self.dummy_time_str, 1)
            out[name] = {
                'name': name,
                'version': version
            }

        return out

    def query_pf9_agent(self):
        """
        Query the installed pf9 host agent details
        :return: dictionary of agent name and version
        :rtype: dict
        """
        for i in range(20):
            version = self._find_installed_pkg_version('pf9-hostagent')
            if len(version) == 1:
                return {
                    'name': 'pf9-hostagent',
                    'version': version[0]
                }
            # Wait for a case where hostagent has restarted on update
            time.sleep(6)

        self.log.error('Could not determine the agent version')
        raise Pf9Exception('Querying pf9 agent version failed.')

    def _find_installed_pkg_version(self, appname):
        """
        Searches the installed packages for an app specified by the app name. The
        search is done based on an absolute match of the app name.
        :param appname: Name of the app to find.
        :return: Version of the appname
        :rtype: list
        """
        version = []
        version_cmd = 'rpm -q %s --queryformat ' %(appname)
        version_cmd = version_cmd + "%{VERSION}-%{RELEASE}\n"

        code, response, err = _run_command_with_custom_pythonpath(version_cmd)
        if code:
            self.log.error('RPM version query command failed : %s. Return code: %d, '
                           'stdout: %s, stderr: %s', version_cmd, code, response, err)
            # In case of failure, empty version list is returned.
            return version

        # Strip trailing newline characters if any, from the response string.
        response = response.rstrip()
        # Convert the response string to the version list.
        version = response.split("\n")
        return version

    def remove_package(self, appname):
        """
        Removes an installed app.
        :param appname: Name of  the app to remove
        :raises NotInstalled: if the app is not found/installed
        :raises RemoveOperationFailed: if the remove operation failed.
        """
        version = self._find_installed_pkg_version(appname)

        if not version:
            # We perform exactmatch above. If nothing is returned, can assume app
            # is not installed
            raise NotInstalled()

        # TODO: verify if this is an issue if same app has 2 versions installed
        # Assert that only a single version of the package is installed.
        assert len(version) == 1

        erase_cmd = 'sudo %s erase %s' % (self.yum_rootwrap_path, appname)
        code, out, err = _run_command_with_custom_pythonpath(erase_cmd)
        if code:
            self.log.error('Erase command failed : %s. Return code: %d, '
                           'stdout: %s, stderr: %s', erase_cmd, code, out, err)
            raise RemoveOperationFailed()

    def install_from_file(self, pkg_path):
        """
        Installs an app from the specified local path
        :param pkg_path: local path to the app to be installed
        :raises InstallOperationFailed: if the install operation failed
        """
        install_cmd = 'sudo %s install %s' % (self.yum_rootwrap_path, pkg_path)
        code, out, err = _run_command_with_custom_pythonpath(install_cmd)
        if code:
            self.log.error('Install command failed : %s. Return code: %d, '
                           'stdout: %s, stderr: %s', install_cmd, code, out, err)
            raise InstallOperationFailed()

    def update_from_file(self, pkg_path):
        """
        Updates a package from the specified local path
        :param str pkg_path: Local path to the package to be upgraded
        :raises OSError: if the file is not found
        :raises UpdateOperationFailed: if the update operation failed.
        """
        update_cmd = 'sudo %s update %s' % (self.yum_rootwrap_path, pkg_path)
        code, out, err = _run_command_with_custom_pythonpath(update_cmd)
        if code:
            self.log.error('Update command failed : %s. Return code: %d, '
                           'stdout: %s, stderr: %s', update_cmd, code, out, err)
            raise UpdateOperationFailed()

class Pf9AppDb(AppDb):
    """ Class that implements the AppDb model interface"""

    def __init__(self, log=logging):
        """
        Constructor
        :param Logger log: logger object for logging
        """
        self.apps = {}
        self.log = log
        self._get_package_manager()

    def _get_package_manager(self):
        """
        Set the package manager depending on the distro being used.
        """
        if get_supported_distro(self.log) == 'debian':
            self.pkgmgr = AptPkgMgr(self.log)
        else:
            self.pkgmgr = YumPkgMgr(self.log)

    def make_app(self, name, version):
        return Pf9App(name, version, self, log=self.log)

    def query_installed_apps(self):
        """
        Returns a dictionary representing installed applications.

        :return: a dictionary mapping app names to App objects
        :rtype: dict
        """
        appMap = {}
        installed = self.pkgmgr.query_pf9_apps()
        for app, val in iteritems(installed):
            appMap[app] = self.make_app(app, val['version'])
        return appMap

    def app_installed(self, app):
        """
        Notify the AppDb that an app was installed.
        :param App app: the app
        """
        pass

    def app_uninstalled(self, app):
        """
        Notify the AppDb that an app was uninstalled.
        :param App app: the app
        """
        pass

    def install_package(self, path):
        """
        Installs an app specified by the path
        :param str path: Path to the app to be installed
        :raises OSError: if the file provided by path is not found
        """
        self.pkgmgr.install_from_file(path)

    def remove_package(self, app_name):
        """
        Remove the specified app
        :param str app_name: Name of the app to be removed
        :raises NotInstalled: if the app is not installed
        """
        self.pkgmgr.remove_package(app_name)


class Pf9AgentDb(Pf9AppDb):
    """
    Class that implements the agent app db interface
    """

    def __init__(self, log=logging):
        """
        Constructor
        :param Logger log: Logger object
        """
        Pf9AppDb.__init__(self, log)


    def update_package(self, path):
        """
        Updates the specified package
        :param str path: Path to the app to be installed
        :raises OSError: if the file provided by path is not found
        """
        self.pkgmgr.update_from_file(path)

    def query_installed_agent(self):
        """
        Queries properties of the installed host agent
        """
        return self.pkgmgr.query_pf9_agent()
