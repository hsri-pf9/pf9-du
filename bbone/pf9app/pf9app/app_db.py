# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'leb'

from abc import ABCMeta, abstractmethod
from app import App

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