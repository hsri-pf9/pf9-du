# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'Platform9'

import copy
import filecmp
import os
import subprocess

from nose import with_setup

from pf9app.app import App
from pf9app.algorithms import process_apps
from pf9app.pf9_app_db import Pf9AppDb
from pf9app.pf9_app_cache import Pf9AppCache
from pf9app.pf9_app import Pf9RemoteApp
from pf9app.pf9_app import Pf9App
from pf9app.exceptions import NotInstalled

TEST_CACHE = '/tmp/pf9app-cache'

def _run_command(command):
    proc = subprocess.Popen(command, shell=True,
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    out, err = proc.communicate()
    code = proc.returncode

    return code, out, err


def _get_test_rpm():
    curdir = os.path.dirname(os.path.realpath(__file__))
    rpmdir = os.path.join(curdir, "..", "..", "..", "build", "pf9-testapp", "rpmbuild")
    return os.path.join(rpmdir, "pf9-testapp-1.0-1.noarch.rpm")

def _app_install():
    _run_command("yum -y install %s" % _get_test_rpm())

def _app_remove():
    _run_command("yum -y remove pf9-testapp")


@with_setup(_app_remove, _app_install)
def test_pf9_appdb():
    app_db = Pf9AppDb()
    result = app_db.query_installed_apps()
    assert type(result) is dict
    assert len(result) == 0

    # Install a package that doesn't exist
    raised = False
    try:
        app_db.install_package("bigfoot")
    except Exception, e:
        raised = True
        assert type(e) is OSError
    assert raised


    rpm = _get_test_rpm()
    assert os.path.exists(rpm)
    try:
        app_db.install_package(rpm)
    except:
        assert False

    result = app_db.query_installed_apps()
    testapp = result['pf9-testapp']
    assert type(testapp) is Pf9App
    assert testapp.app_name == 'pf9-testapp'
    assert testapp.app_version == '1.0-1'

    try:
        app_db.remove_package("pf9-testapp")
    except:
        assert False

    result = app_db.query_installed_apps()
    assert len(result) == 0

    # Remove a package that doesn't exist
    raised = False
    try:
        app_db.remove_package("bigfoot")
    except Exception, e:
        raised = True
        assert type(e) is NotInstalled
    assert raised


@with_setup(_app_install, _app_remove)
def test_pf9_app():
    app_db = Pf9AppDb()
    result = app_db.query_installed_apps()
    assert result['pf9-testapp']

    testapp = result['pf9-testapp']
    assert testapp.app_name == 'pf9-testapp'
    assert testapp.app_version == '1.0-1'
    assert not testapp.running

    testapp.set_run_state(True)
    assert testapp.running

    testapp.set_run_state(False)
    assert not testapp.running

    try:
        config = testapp.get_config()
    except:
        assert False

    assert type(config) is dict
    assert config['section1']['key2'] == 'val2'
    assert config['section2']['key3'] == 'val3'

    newconfig = copy.deepcopy(config)
    newconfig['section2']['key4'] = 'newval4'
    try:
        testapp.set_config(newconfig)
    except:
        assert False

    try:
        config = testapp.get_config()
    except:
        assert False

    assert config == newconfig

    try:
        testapp.uninstall()
    except:
        assert False


def _cache_setup():
    _run_command("rm -rf %s" % TEST_CACHE)
    _run_command("mkdir %s" % TEST_CACHE)

def _cache_teardown():
    _run_command("rm -rf %s" % TEST_CACHE)


@with_setup(_cache_setup, _cache_teardown)
def test_pf9_appcache():

    app_cache = Pf9AppCache(TEST_CACHE)
    src_rpm = _get_test_rpm()
    rpm_url = "file://%s" % src_rpm
    local_path = app_cache.download('pf9-testapp', '1.0-1', rpm_url)
    assert os.path.exists(local_path)
    assert filecmp.cmp(src_rpm, local_path)

    # If the app was already downloaded, it should return it from cache
    # Simulate this with a bad URL and verify download reports path
    local_path = None
    local_path = app_cache.download('pf9-testapp', '1.0-1', None)
    assert os.path.exists(local_path)
    assert filecmp.cmp(src_rpm, local_path)


def _remoteapp_setup():
    _cache_setup()
    _app_remove()

def _remoteapp_teardown():
    _cache_teardown()
    _app_remove()

@with_setup(_remoteapp_setup, _remoteapp_teardown)
def test_pf9_remoteapp():
    app_cache = Pf9AppCache(TEST_CACHE)
    app_db = Pf9AppDb()
    src_rpm = _get_test_rpm()
    rpm_url = "file://%s" % src_rpm
    remote_app = Pf9RemoteApp('pf9-testapp', '1.0-1', rpm_url, app_db, app_cache)
    try:
        local_path = remote_app.download()
    except:
        assert False
    assert os.path.exists(local_path)
    assert filecmp.cmp(src_rpm, local_path)

    try:
        remote_app.install()
    except:
        assert False

    result = app_db.query_installed_apps()
    testapp = result['pf9-testapp']
    assert testapp.app_name == 'pf9-testapp'
    assert testapp.app_version == '1.0-1'
