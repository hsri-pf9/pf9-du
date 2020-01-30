# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'leb'

from abc import ABCMeta, abstractmethod
from pf9app.app import App
from six import iteritems

class AppDb(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def query_installed_apps(self):
        """
        Returns a dictionary representing installed applications.

        :return: a dictionary mapping app names to App objects
        :rtype: dict
        """
        pass

    @abstractmethod
    def app_installed(self, app):
        """
        Notify the AppDb that an app was installed.
        :param App app: the app
        """
        pass

    @abstractmethod
    def app_uninstalled(self, app):
        """
        Notify the AppDb that an app was uninstalled.
        :param App app: the app
        """
        pass

    def install_package(self, path):
        """
        Installs the app represented by the path
        :param path: Local path to the app package
        """
        pass

    def remove_package(self, app_name):
        """
        Removes a particular app from the host
        :param app_name: Name of the app to be removed, like 'gcc'
        """
        pass

    def update_package(self, path):
        """
        Updates a particular package on the host
        :param str path: Local path to the package to be upgraded
        """
        pass

    def make_app(self, name, version):
        """
        Returns an installed app object from package name and version
        :param name: Name of package
        :param version: Version of package
        """
        pass

    def get_current_config(self):
        """
        Computes the current application configuration.
        :return: a dictionary representing the aggregate app configuration.
        :rtype: dict
        """
        apps = self.query_installed_apps()
        config = {}
        for app_name, app in iteritems(apps):
            if app.implements_service_states:
                config[app_name] = {
                    'version': app.version,
                    'config': app.get_config(),
                    'service_states': app.get_service_states()
                }
            else:
                config[app_name] = {
                    'version': app.version,
                    'running': app.running,
                    'config': app.get_config()
                }
        return config
