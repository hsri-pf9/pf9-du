# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'Platform9'

import errno
import logging
import os
import subprocess
import yum

from app_db import AppDb
from pf9_app import Pf9App
from exceptions import NotInstalled, UpdateOperationFailed, \
    RemoveOperationFailed, InstallOperationFailed


def _run_command(command):
    """
    Run a command
    :param str command: Command to be executed.
    :return: a tuple representing (code, stdout, stderr), where code is the
             return code of the command, stdout is the standard output of the
             command and stderr is the stderr of the command
    :rtype: tuple
    """
    proc = subprocess.Popen(command, shell=True,
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    out, err = proc.communicate()
    code = proc.returncode

    return code, out, err


class YumPkgMgr(object):
    """Class that interacts with the YUM package manager"""

    # TODO: Consider building a package manager interface to denote all the methods
    # that need to be implemented as part of the package manager.

    def __init__(self, log = logging):
        self.ybase = yum.YumBase()
        self.log = log

    def query_pf9_apps(self):
        """
        Query the installed packages on the machine that are pf9 apps. Packages
        that provide "pf9app" are considered as pf9 apps

        :return: dict of pf9 apps mapped to its details (name, version)
        :rtype: dict
        """
        out = {}
        # We need to refresh the RPM DB, otherwise we won't discover the latest
        # set of apps which may have been installed outside of this YumBase
        # instance
        self.ybase.closeRpmDB()
        pkgs = self.ybase.rpmdb.searchProvides("pf9app")
        for pkg in pkgs:
            out[pkg.name] = {
                'name': pkg.name,
                'version': pkg.printVer()
            }

        return out

    def query_pf9_agent(self):
        """
        Query the installed pf9 host agent details from the YUM repo
        :return: dictionary of agent name and version
        :rtype: dict
        """
        pkgs = self._find_installed_pkg('pf9-hostagent')
        assert len(pkgs) == 1
        return {
            'name': pkgs[0].name,
            'version': pkgs[0].printVer()
        }

    def _find_installed_pkg(self, appname):
        """
        Searches the installed packages for an app specified by the app name. The
        search is done based on an absolute match of the app name.
        :param appname: Name of the app to find.
        :return: List of yum.rpmsack.RPMInstalledPackage objects that match the search
        :rtype: list
        """
        pkgs = self.ybase.doPackageLists('installed')
        exactmatch, _, _ = yum.packages.parsePackages(pkgs.installed, [appname])
        return exactmatch

    def remove_package(self, appname):
        """
        Removes an installed app.
        :param appname: Name of  the app to remove
        :raises NotInstalled: if the app is not found/installed
        :raises RemoveOperationFailed: if the remove operation failed.
        """
        pkgs = self._find_installed_pkg(appname)

        if not pkgs:
            # We perform exactmatch above. If nothing is returned, can assume app
            # is not installed
            raise NotInstalled()

        # match for pkg should be only 1, since it is an exact match
        # TODO: verify if this is an issue if same app has 2 versions installed
        assert len(pkgs) == 1

        erase_cmd = 'yum -y erase %s' % appname
        code, out, err = _run_command(erase_cmd)
        if code:
            self.log.error('Erase command failed : %s. Return code: %d, '
                           'stdout: %s, stderr: %s', erase_cmd, code, out, err)
            raise RemoveOperationFailed()

    def install_from_file(self, pkg_path):
        """
        Installs an app from the specified local path
        :param pkg_path: Local path to the app to be installed
        :raises OSError: if the file is not found.
        :raises InstallOperationFailed: if the install operation failed
        """
        if not os.path.exists(pkg_path):
            # File to install doesn't exist
            raise OSError(errno.ENOENT, os.strerror(errno.ENOENT), pkg_path)

        install_cmd = 'yum -y install %s' % pkg_path
        code, out, err = _run_command(install_cmd)
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
        if not os.path.exists(pkg_path):
            # File to update doesn't exist
            raise OSError(errno.ENOENT, os.strerror(errno.ENOENT), pkg_path)

        # Ideally, we want to use YUM API for this. However, we are using this
        # for in place update of the host agent only. That operation will not
        # work cleanly with YUM API (end up with multiple host agents because
        # YUM marks the removal of previous host agent as incomplete)
        update_cmd = 'yum -y update %s' % pkg_path
        code, out, err = _run_command(update_cmd)
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
        # Currently, assumed that only YUM is supported. This will eventually
        # have to be distro specific
        self.pkgmgr = YumPkgMgr(log)
        self.log = log

    def query_installed_apps(self):
        """
        Returns a dictionary representing installed applications.

        :return: a dictionary mapping app names to App objects
        :rtype: dict
        """
        appMap = {}
        installed = self.pkgmgr.query_pf9_apps()
        for app, val in installed.iteritems():
            appMap[app] = Pf9App(app, val['version'], self)

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