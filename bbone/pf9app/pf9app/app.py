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

    @property
    @abstractmethod
    def services(self):
        """
        Returns the app's list of services
        Returns an empty list if there are no services to manage
        :rtype: list
        """
        pass

    @property
    @abstractmethod
    def implements_service_states(self):
        """
        Returns True if the app implements the new way of managing services
        The new way means we have a dictionary of services to manage which may
        be empty.
        The old way assumes that there is only one such service to manage which
        has the same name as the app.
        :rtype: bool
        """
        pass

    @abstractmethod
    def has_desired_service_states(self, desired):
        """
        Returns True if Pf9App has the desired running state for each service
        :param dict desired: a dictionary of services to check where the
        keys are the names of the services and values are booleans corresponding
        to their desired running state.
        {
            "pf9-ostackhost": True,
            "pf9-novncproxy": False
        }
        :rtype: bool
        """
        pass

    @abstractmethod
    def set_desired_service_states(self, services, stop_all=False):
        """
        Sets the desired running state for each service.
        :param dict services: a dictionary containing services and their
            desired states
        """
        pass

    @abstractmethod
    def get_service_states(self):
        """
        Returns a dictionary of services along with their running states
        :rtype: dict
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


