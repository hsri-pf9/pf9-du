# Copyright 2015 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'Platform9'

from bbcommon.exceptions import Pf9FirmwareAppsError
from glob import glob
from os import path, environ
import logging
from bbmaster import pf9_comms
from bbmaster import pf9_vmw_mgmt
from bbmaster import pf9_muster
import subprocess

LOG = logging.getLogger(__name__)

# TODO: Load these modules dynamically
firmware_apps_cdu = { 'pf9-comms': pf9_comms, 'pf9-vmw-mgmt': pf9_vmw_mgmt, 'pf9-muster': pf9_muster }
firmware_apps_ddu = { 'pf9-comms': pf9_comms }

def get_firmware_apps(is_ddu=False):
    if is_ddu == True:
        return firmware_apps_ddu
    return firmware_apps_cdu

def get_package_version_cdu(package_name, app_name):
    """
    This function extracts information from rpm package file and returns version information.
    Input params:
        1. package_name - Path to the package file
        2. app_name - application name
    Output params:
        1. version of the package
    Exception: On failure of command.
    """
    args = ['/bin/rpm', '-qp', '--qf', '%{VERSION}-%{RELEASE}', package_name]
    cmd = subprocess.Popen(args, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE)
    version, stderr = cmd.communicate()
    if cmd.returncode != 0:
        LOG.error('query of {app} RPM failed: {err}'.format(err=stderr,
                                                            app=app_name))
        raise Pf9FirmwareAppsError
    return version

def get_package_version_ddu(package_name, app_name):
    """
    This function extracts information from debian package file and returns version information.
    Input params:
        1. package_name - Path to the package file
        2. app_name - application name
    Output params:
        1. version of the package
    Exception: On failure of command.
    """
    command='version_out=`dpkg --info ' + package_name + \
        '`; if [ "$?" != "0" ]; then exit 1; else echo "$version_out" | grep Version | cut -d \':\' -f2; fi'
    proc = subprocess.run(['/bin/bash', '-c', command], stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    version, stderr = proc.stdout.strip(), proc.stderr
    LOG.info('query of {app} DEB returned version {ver} and returncode {retcode}'.format(
            app=app_name,
            ver=version,
            retcode=proc.returncode))
    if proc.returncode != 0:
            LOG.error('query of {app} DEB failed: {err}'.format(err=stderr,
                                                                app=app_name))
            raise Pf9FirmwareAppsError
    if len(version) == 0:
            LOG.error('query of {app} DEB failed: version found to be empty'.format(
                                                                app=app_name))
            raise Pf9FirmwareAppsError
    return version.strip()

def _app_package_and_version(app_name, base_dir, is_ddu=False):
    name = app_name.upper().replace('-', '_')
    version_key = '%s_VERSION' % name
    package_key = '%s_FILENAME' % name
    if version_key in environ and package_key in environ:
        return environ[package_key], environ[version_key]
    # NOTE: Even though the packages can be rpm or deb files, we
    # still pass rpm file paths because hostagent does the logic
    # of whether to download the rpm or deb file.
    # https://github.com/platform9/pf9-du/blob/atherton/bbone/pf9app/pf9app/pf9_app_cache.py#L152
    pattern = '{app_dir}/{app}*.rpm'
    expr = pattern.format(app_dir=base_dir, app=app_name)
    pkgs = glob(expr)
    if len(pkgs) != 1:
        LOG.error('Number of {app} packages found: {num}'.format(app=app_name,
                                                             num=len(pkgs)))
        raise Pf9FirmwareAppsError
    version = ""
    # get rpm version for classic DU and get debian version from DDU as
    # DDU container is debian based.
    if is_ddu == False:
        version = get_package_version_cdu(pkgs[0], app_name)
    else:
        version = get_package_version_ddu(pkgs[0], app_name)
    version = version.decode()
    LOG.info('Version of {app} found to be {ver}'.format(app=app_name, ver=version))
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


def get_fw_apps_cfg(config=None, is_ddu=False):
    apps_config = {}
    firmware_apps = get_firmware_apps(is_ddu)
    for app_name, module in firmware_apps.items():
        # Get the config that is specific to each service / app.
        service_config = module.get_service_config()
        base_dir, base_url = _get_base_dir_url(app_name, config)
        pkg_file, version = _app_package_and_version(app_name, base_dir, is_ddu=is_ddu)
        service_config['version'] = version
        service_config['url'] = '%s/%s' % (base_url, pkg_file)
        apps_config[app_name] = service_config
    return apps_config


def insert_fw_apps_config(desired_apps, fw_apps_config, host_state=None, is_ddu=False):
    # Let each firmware module decide whether to insert its app into
    # the configuration
    # TODO: Add firmware app config to desired_apps in this functions instead
    #       of doing it in modules.
    firmware_apps = get_firmware_apps(is_ddu)
    for app_name, module in firmware_apps.items():
        module.insert_app_config(desired_apps,
                                 fw_apps_config[app_name],
                                 host_state=host_state)
    return desired_apps


def remove_fw_apps_config(hosts, is_ddu=False):
    firmware_apps = get_firmware_apps(is_ddu)
    for host in hosts:
        for key in ('apps', 'desired_apps'):
            if key in host:
                for app in firmware_apps:
                    host[key].pop(app, None)
    return hosts
