# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'Platform9'

import errno
import logging
import os
import yum

from app_db import AppDb
from pf9_app import Pf9App
from exceptions import NotInstalled


class YumPkgMgr(object):
    """Class that interacts with the YUM package manager"""

    # TODO: Consider building a package manager interface to denote all the methods
    # that need to be implemented as part of the package manager.

    def __init__(self):
        self.ybase = yum.YumBase()

    def query_pf9_apps(self):
        """
        Query the installed packages on the machine that are pf9 apps. Packages
        that provide "pf9app" are considered as pf9 apps

        :return: dict of pf9 apps mapped to its details (name, version)
        :rtype: dict
        """
        out = {}

        pkgs = self.ybase.rpmdb.searchProvides("pf9app")
        for pkg in pkgs:
            out[pkg.name] = {
                'name': pkg.name,
                'version': pkg.printVer()
            }

        return out

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
        """
        pkgs = self._find_installed_pkg(appname)

        if not pkgs:
            # We perform exactmatch above. If nothing is returned, can assume app
            # is not installed
            raise NotInstalled()

        # match for pkg should be only 1, since it is an exact match
        # TODO: verify if this is an issue if same app has 2 versions installed
        assert len(pkgs) == 1

        self.ybase.remove(pkgs[0])
        self.ybase.buildTransaction()
        self.ybase.processTransaction()

    def install_from_file(self, pkgpath):
        """
        Installs an app from the specified local path
        :param pkgpath: Local path to the app to be installed
        :raises OSError: if the file is not found.
        """
        if not os.path.exists(pkgpath):
            # File to install doesn't exist
            raise OSError(errno.ENOENT, os.strerror(errno.ENOENT), pkgpath)

        self.ybase.installLocal(pkgpath)
        self.ybase.buildTransaction()
        self.ybase.processTransaction()


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
        self.pkgmgr = YumPkgMgr()
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
