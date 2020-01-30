# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'leb'
import pf9app.exceptions
import logging

from pf9app.app_db import AppDb
from pf9app.app import App

class MockAppDb(AppDb):

    def __init__(self, log=logging):
        self.apps = {}

    def query_installed_apps(self):
        return self.apps

    def app_installed(self, app):
        assert isinstance(app, App)
        if app.name in self.apps:
            raise exceptions.AlreadyInstalled()
        self.apps[app.name] = app

    def app_uninstalled(self, app):
        assert isinstance(app, App)
        if app.name not in self.apps:
            raise exceptions.NotInstalled()
        del self.apps[app.name]

    def query_installed_agent(self):
        return {
            'name': 'mock-hostagent',
            'version': '1.0.1-1'
        }

    def make_app(self, name, version):
        assert self.apps[name].version == version
        return self.apps[name]
