# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'Platform9'

import logging
import json
import os
import subprocess
import sys

from exceptions import ServiceCtrlError, ConfigOperationError
from app import App, RemoteApp

CFGSCRIPTCMD = "%s /opt/pf9/%s/config"
SERVICECMD = "sudo service %s %s"


def prune_pf9_python_path():
    """
    Removes the Platform9 specific python path if it exists in the environment
    """
    pf9_python_path = '/opt/pf9/python/lib/python2.7:'
    run_env = os.environ

    if pf9_python_path in os.environ.get('PYTHONPATH', ''):
        run_env = copy.deepcopy(os.environ)
        run_env["PYTHONPATH"] = run_env['PYTHONPATH'].replace(pf9_python_path, '')

    return run_env


ORIG_PYTHON_PATH = prune_pf9_python_path()


def _run_command(command, stdout=subprocess.PIPE, run_env=os.environ):
    """
    Runs a command
    :param str command: Command to be executed.
    :return: a tuple representing (code, stdout, stderr), where code is the
    return code of the command, stdout is the standard output of the command and
    stderr is the stderr of the command
    :rtype: tuple
    """
    # NOTE: There is an oddity noticed with subprocess. Once invoked with the
    # env parameter, subsequent calls without the env parameter don't seem to
    # reset the environment to run the command. Needs more investigation. Till
    # then, always pass an appropriate env parameter.
    proc = subprocess.Popen(command, shell=True,
                            stdin=subprocess.PIPE,
                            stdout=stdout,
                            stderr=subprocess.PIPE,
                            env=run_env)
    out, err = proc.communicate()
    code = proc.returncode

    return code, out, err


def _run_command_with_custom_pythonpath(command):
    """
    Runs a command with the custom Platform9 python path removed. This should
    allow the command to leverage the global python modules
    :param str command: Command to be executed.
    :return: a tuple representing (code, stdout, stderr), where code is the
    return code of the command, stdout is the standard output of the command and
    stderr is the stderr of the command
    :rtype: tuple
    """
    return _run_command(command, run_env=ORIG_PYTHON_PATH)


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
        self.log.debug("Command %s, code=%d stdout=%s stderr=%s",
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

    def _get_services(self):
        """
        Returns a 2-tuple.
        The first element is boolean flag which tells us whether the config script
            implements the '--get-services' option.
        The second element is a list of services to manage.
        :rtype: (bool, list)
        """
        cfgscript = self._get_config_script()

        # The script shall return a non zero return code in case of an error
        code, out, err = _run_command("%s --get-services" % cfgscript)
        if code:
            self.log.debug("%s does not implement the --get-services option. Falling back to compatibility mode",
                self.app_name)
            return False, []

        if len(out) > 0:
            return True, out.split(' ')
        else:
            return True, []

    @property
    def services(self):
        """
        Returns the app's list of services using the config script.
        Returns an empty list if option returns a non-zero exit code
            or if the config script returns an empty string--which
            means there are no services to manage.
        :rtype: list
        """
        implements_service_states, service_list = self._get_services()
        return service_list

    @property
    def implements_service_states(self):
        """
        Returns True if the config script implements the --get-services option.
        :rtype: bool
        """
        implements_service_states, service_list = self._get_services()
        return implements_service_states

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
        self.log.debug("Checking whether services have the desired state")
        if self.implements_service_states:
            current_state = self.get_service_states()
        else:
            current_state = { self.app_name: self.running }
        return current_state == desired

    def set_desired_service_states(self, services, stop_all=False):
        """
        Sets the desired running state for each service.
        :param dict services: a dictionary of services
        :param bool stop_all: a flag to signal to stop all services
            used during uninstalls
        :raises ServiceCtrlError: if the service state change operation fails
        """
        self.log.info("Setting the desired service state")

        for name, service_state in services.iteritems():
            run_state = False if stop_all else service_state
            self._set_run_state(name, run_state)

    def get_service_states(self):
        """
        Returns a dictionary of services along with their running states.
        :rtype: dict

        {
            "pf9-ostackhost": True ,
            "pf9-novncproxy": True
        }
        """
        services_dict = {}
        for service_name in self.services:

            cmd = SERVICECMD % (service_name, "status")
            code, out, err = _run_command(cmd)
            self.log.debug("Command %s, code=%d stdout=%s stderr=%s",
                cmd, code, out, err)

            # Refer to LSB specification for the codes. If code is 0, then service is
            # assumed to be running.
            services_dict[service_name] = code == 0
        return services_dict

    def _set_run_state(self, service, run_state):
        """
        Starts or stops a service.
        :param bool run_state: Whether the service should be running.
        :raises ServiceCtrlError: if the service state change operation fails
        """
        cmd = SERVICECMD % (service, "start" if run_state else "stop")
        self.log.info("Setting service state %s.%s. Command: %s",
                      service, self.version, cmd)
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
        return CFGSCRIPTCMD % (sys.executable, self.app_name)

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
        self.log.info("Setting config for %s.%s", self.name, self.version)
        code, out, err = _run_command("%s --set-config '%s'" % (cfgscript, json.dumps(config)))
        if code:
            self.log.error(("%s:set_config failed:\nout: %s\nerr: %s\ncommand: "
                                "%s --set-config '%s'"),
                           self.app_name, out, err, cfgscript,
                           json.dumps(config))
            raise ConfigOperationError()

    def uninstall(self):
        """
        Uninstalls the application.

        Stops the services if they are running.
        :raises ServiceCtrlError: if stopping the service(s) fails before the uninstall
        """
        self.log.info("Removing %s.%s", self.name, self.version)
        # Stop the running service(s) first
        if self.implements_service_states:
            services = self.get_service_states()
        else:
            services = { self.app_name: self.running }
        self.set_desired_service_states(services, stop_all=True)

        # Stop service will raise an exception if it fails, uninstall will be
        # called only if that succeeds
        self.app_db.remove_package(self.app_name)
        self.log.info("%s.%s removed successfully", self.name, self.version)


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
        Pf9App.__init__(self, name=name, version=version, app_db=app_db, installed=False, log=log)
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


class Pf9AgentApp(Pf9RemoteApp):
    """
    Class that implements the host agent app interface
    """
    def __init__(self, name, version, url, app_db, app_cache, log=logging):
        """
        Constructor
        :param str name: Name of the agent
        :param str version: Version of the agent
        :param str url: URL from where the agent can be downloaded.
        :param AppDb app_db: database of installed agents
        :param AppCache app_cache: cache of agent apps
        :param Logger log: logger object for logging
        """
        Pf9RemoteApp.__init__(self, name=name, version=version, url=url,
                              app_db=app_db, app_cache=app_cache, log=log)

    def update(self):
        """
        Updates the host agent running on the host
        """
        self.log.info('Updating %s.%s', self.name, self.version)

        local_path = self.download()
        self.app_db.update_package(local_path)
        self.log.info('%s.%s updated successfully', self.name, self.version)
