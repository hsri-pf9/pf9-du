# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'leb'

import pf9app.exceptions
from pf9app.app import App, RemoteApp
import re
import copy
import logging

class MockInstalledApp(App):
    def __init__(self, name, version, app_db,
                 running=False, installed=True, config={}, log=logging):
        self.app_name = name
        self.app_version = version
        self.app_run_state = running
        self.config = config
        self.app_db = app_db
        self.installed = True if running else installed
        self.log = log

    @property
    def name(self):
        return self.app_name

    @property
    def running(self):
        assert self.installed
        return self.app_run_state

    @property
    def version(self):
        return self.app_version

    def set_run_state(self, run_state):
        assert self.installed
        self.log.info('Setting run state of %s %s to %s',
                 self.app_name, self.app_version, run_state)
        self.app_run_state = run_state

    def get_config(self):
        return self.config

    def set_config(self, config):
        self.log.info('Changing configuration for %s %s',
                 self.app_name, self.app_version)
        self.config = copy.deepcopy(config)

    def uninstall(self):
        self.log.info('Uninstalling %s %s', self.app_name, self.app_version)
        self.installed = False
        self.app_db.app_uninstalled(self)


class MockRemoteApp(MockInstalledApp, RemoteApp):
    def __init__(self, name, version, url, app_db, app_cache, log=logging):
        """
        Initializes mock remote app.
        :param str name: application name
        :param str version: application version
        :param url: download URL
        :param AppDb app_db: app database
        :param AppCache app_cache: app cache
        :return:
        """

        # If the url is of the form http://..../pkgname-xx.yy.rpm then
        # we interpret xx.yy as the version. This allows us to simulate
        # cases where the specified version and the actual version differ.
        m = re.match('.*/\w*-(\d+\.\d+)\.rpm', url)
        if m:
            version = m.groups()[0]

        MockInstalledApp.__init__(self,
                                  name=name,
                                  version=version,
                                  app_db=app_db,
                                  installed=False,
                                  log=log)
        self.url = url
        self.app_cache = app_cache
        self.local_path = None

    def install(self):
        if self.installed:
            return
        if not self.local_path:
            raise pf9app.exceptions.NotDownloaded()
        self.log.info('Installing %s %s', self.app_name, self.app_version)
        self.installed = True
        self.app_db.app_installed(self)

    def download(self):
        self.log.info('Downloading %s %s from %s',
                 self.app_name, self.app_version, self.url)
        self.local_path = self.app_cache.download(name=self.app_name,
                                                  version=self.app_version,
                                                  url=self.url)

