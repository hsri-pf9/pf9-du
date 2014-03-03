# Copyright 2013 Platform9 Systems Inc.
# All Rights Reserved.

'''
Defines the interface for a PF9 application
'''

__author__ = 'leb'

from abc import ABCMeta, abstractmethod

class App(object):
    """
    Models an installed pf9 application
    """
    __metaclass__ = ABCMeta

    @property
    @abstractmethod
    def name(self):
        pass

    @property
    @abstractmethod
    def running(self):
        """
        Whether the app is running.
        :rtype: bool
        """
        pass

    @property
    @abstractmethod
    def version(self):
        """
        The app's current version string.
        :rtype: str
        """
        pass

    @abstractmethod
    def get_config(self):
        """
        Returns the app's current configuration.
        :return: a dictionary
        :rtype: dict
        """
        pass

    @abstractmethod
    def set_config(self, config):
        """
        Sets new configuration for the app.

        If the app is running, this will cause it to reload or restart.
        :param dict config: new configuration
        :return:
        """
        pass

    @abstractmethod
    def uninstall(self):
        """
        Uninstalls the application.

        Stops it first if it is running.
        """
        pass

    @abstractmethod
    def set_run_state(self, run_state):
        """
        Starts or stops the application.
        :param bool run_state: Whether the app should be running.
        """
        pass


class RemoteApp(App):
    """
    An app that needs to be downloaded and installed before being used
    """
    @abstractmethod
    def download(self):
        """
        Downloads the file from the source url of the app to the local cache
        :return: path to local downloaded file
        :rtype: str
        """
        pass

    @abstractmethod
    def install(self):
        """
        Installs an app. This shall also download the app to the local cache if
        it has not been downloaded already.
        """
        pass


