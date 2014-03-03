# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'Platform9'

import logging
import json
import os
import subprocess

from exceptions import ServiceCtrlError, ConfigOperationError
from app import App, RemoteApp

CFGSCRIPTBASEDIR = "/opt/pf9/%s/config"
SERVICECMD = "/sbin/service %s %s"


def _run_command(command):
    """
    :param str command: Command to be executed.
    :return: a tuple representing (code, stdout, stderr), where code is the
    return code of the command, stdout is the standard output of the command and
    stderr is the stderr of the command
    :rtype: tuple
    """
    proc = subprocess.Popen(command, shell=True,
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    out, err = proc.communicate()
    code = proc.returncode

    return code, out, err


class Pf9App(App):
    """ Implementation of the App Interface for Platform9 apps"""

    def __init__(self, name, version, app_db, installed=True, log=logging):
        """
        Constructor
        :param str name: Name of the pf9 app
        :param str version: Version of the pf9 app
        :param AppDb app_db: Instance of the pf9 appDb
        :param bool installed: Should be True if the app is installed
        :param Logger log: Logger to be used
        """
        self.app_name = name
        self.app_version = version
        self.app_db = app_db
        self.app_installed = installed
        self.log = log

    @property
    def name(self):
        """
        Name of the app
        :rtype: str
        """
        return self.app_name

    @property
    def running(self):
        """
        Whether the app is running.
        :rtype: bool
        """
        cmd = SERVICECMD % (self.app_name, "status")
        code, out, err = _run_command(cmd)
        self.log.info("Command %s, code=%d stdout=%s stderr=%s",
                      cmd, code, out, err)
        # Refer to LSB specification for the codes. If code is 0, then service is
        # assumed to be running.
        return code == 0

    @property
    def version(self):
        """
        Version of the app
        :rtype: str
        """
        return self.app_version

    def set_run_state(self, run_state):
        """
        Starts or stops the application.
        :param bool run_state: Whether the app should be running.
        :raises ServiceCtrlError: if the service state change operation fails
        """
        cmd = SERVICECMD % (self.app_name, "start" if run_state else "stop")
        code, out, err = _run_command(cmd)
        if code:
            self.log.error("Command %s, code=%d stdout=%s stderr=%s",
                           cmd, code, out, err)
            raise ServiceCtrlError()

    def _get_config_script(self):
        """
        Returns the config script path for the app
        :return: Path to the config script
        :rtype: str
        """
        return CFGSCRIPTBASEDIR % self.app_name

    def get_config(self):
        """
        Returns the app's current configuration.
        :return: a dictionary
        :rtype: dict
        :raises ConfigOperationError: if getting the config failed
        """
        cfgscript = self._get_config_script()

        # The script shall return a non zero return code in case of an error
        code, out, err = _run_command("%s --get-config" % cfgscript)
        if code:
            self.log.error("%s:get_config failed: %s %s", self.app_name, out, err)
            raise ConfigOperationError()
        try:
            cfg = json.loads(out)
        except ValueError, e:
            self.log.error("%s:get_config output is malformed: %s",
                           self.app_name, e)
            raise ConfigOperationError()
        return cfg


    def set_config(self, config):
        """
        Sets new configuration for the app.

        If the app is running, this will cause it to reload or restart.
        :param dict config: new configuration
        :raises ConfigOperationError: if setting the config fails
        """
        cfgscript = self._get_config_script()

        # NOTE: The set-config should take care of restarting/reloading the app.
        # There is no need to do this as part of this method

        # The script shall return a non zero return code in case of an error
        code, out, err = _run_command("%s --set-config '%s'" % (cfgscript, json.dumps(config)))
        if code:
            self.log.error("%s:set_config failed: %s %s", self.app_name, out, err)
            raise ConfigOperationError()


    def uninstall(self):
        """
        Uninstalls the application.

        Stops it first if it is running.
        :raises ServiceCtrlError: if stopping the service fails before the uninstall
        """

        # Stop the running service first
        self.set_run_state(False)

        # Stop service will raise an exception if it fails, uninstall will be
        # called only if that succeeds
        self.app_db.remove_package(self.app_name)


class Pf9RemoteApp(Pf9App, RemoteApp):
    """Class that implements the RemoteApp interface"""

    def __init__(self, name, version, url, app_db, app_cache, log=logging):
        """
        Constructor
        :param str name: Name of the app
        :param str version: Version of the app
        :param str url: Url for downloading the app
        :param AppDb app_db: Instance of the AppDb
        :param AppCache app_cache: Instance of the AppCache
        :param Logger log: Log handler object.
        """
        Pf9App.__init__(self, name=name, version=version, app_db=app_db,  installed=False, log=log)
        self.url = url
        self.appcache = app_cache


    def install(self):
        """
        Installs an app. This shall download the app to the local cache if it
        has not been downloaded already.
        :raises DownloadFailed: if the download of the app failed
        :raises OSError: if the app was not found in the local cache
        """
        self.log.info("Installing %s.%s", self.name, self.version)
        # If the app already is downloaded, this just returns the local path
        # from its cache. If not, it will download it.
        localpath = self.download()
        self.app_db.install_package(localpath)
        self.log.info("%s.%s installed successfully", self.name, self.version)


    def download(self):
        """
        Downloads the file from the source url of the app to the local cache
        :return: path to local downloaded file
        :rtype: str
        :raises DownloadFailed: if the download of the app failed.
        """
        return self.appcache.download(self.name, self.version, self.url)
