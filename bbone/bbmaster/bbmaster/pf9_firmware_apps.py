# Copyright 2015 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'Platform9'

from bbcommon.exceptions import Pf9FirmwareAppsError
from glob import glob
from os import path, environ
import logging
import pf9_comms
import pf9_vmw_mgmt
import pf9_muster
import subprocess

LOG = logging.getLogger(__name__)

# TODO: Load these modules dynamically
firmware_apps = { 'pf9-comms': pf9_comms, 'pf9-vmw-mgmt': pf9_vmw_mgmt, 'pf9-muster': pf9_muster }


def _app_package_and_version(app_name, base_dir):
    name = app_name.upper().replace('-', '_')
    version_key = '%s_VERSION' % name
    package_key = '%s_FILENAME' % name
    if version_key in environ and package_key in environ:
        return environ[package_key], environ[version_key]

    expr = '{app_dir}/{app}*.rpm'.format(app_dir=base_dir, app=app_name)
    pkgs = glob(expr)
    if len(pkgs) != 1:
        LOG.error('Number of {app} RPMs found: {num}'.format(app=app_name,
                                                             num=len(pkgs)))
        raise Pf9FirmwareAppsError
    args = ['/bin/rpm', '-qp', '--qf', '%{VERSION}-%{RELEASE}', pkgs[0]]
    cmd = subprocess.Popen(args, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
    version, stderr = cmd.communicate()
    if cmd.returncode != 0:
        LOG.error('query of {app} RPM failed: {err}'.format(err=stderr,
                                                            app=app_name))
        raise Pf9FirmwareAppsError
    pkg_filename = path.basename(pkgs[0])
    return pkg_filename, version


def _get_base_dir_url(app_name, config=None):
    # Get the base dir and URL from conf if specified there. Conf keys are named
    # comms_baseurl, comms_basedir, etc.
    name = app_name.replace('-', '_').replace('pf9_', '')
    basedir_key = "%s_basedir" % name
    baseurl_key = "%s_baseurl" % name
    basedir = config.get('bbmaster', basedir_key) if \
        config and config.has_option('bbmaster', basedir_key) else \
        '/opt/pf9/www/private'
    baseurl = config.get('bbmaster', baseurl_key) if \
        config and config.has_option('bbmaster', baseurl_key) else \
        '%(download_protocol)s://%(host_relative_amqp_fqdn)s:%(download_port)s/private'
    return basedir, baseurl


def get_fw_apps_cfg(config=None):
    apps_config = {}
    for app_name, module in firmware_apps.items():
        # Get the config that is specific to each service / app.
        service_config = module.get_service_config()
        base_dir, base_url = _get_base_dir_url(app_name, config)
        pkg_file, version = _app_package_and_version(app_name, base_dir)
        service_config['version'] = version
        service_config['url'] = '%s/%s' % (base_url, pkg_file)
        apps_config[app_name] = service_config
    return apps_config


def insert_fw_apps_config(desired_apps, fw_apps_config, host_state=None):
    # Let each firmware module decide whether to insert its app into
    # the configuration
    # TODO: Add firmware app config to desired_apps in this functions instead
    #       of doing it in modules.
    for app_name, module in firmware_apps.items():
        module.insert_app_config(desired_apps,
                                 fw_apps_config[app_name],
                                 host_state=host_state)
    return desired_apps


def remove_fw_apps_config(hosts):
    for host in hosts:
        for key in ('apps', 'desired_apps'):
            if key in host:
                for app in firmware_apps:
                    host[key].pop(app, None)
    return hosts
