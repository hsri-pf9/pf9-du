import json
import os
from six.moves.configparser import ConfigParser
import shutil

HOSTID_CONF = '/etc/pf9/host_id.conf'

def clean_packages(log):
    log.info('Cleaning old packages from /var/cache/pf9apps')
    if not os.path.isfile(HOSTID_CONF):
        return
    config = ConfigParser()
    try:
        config.read(HOSTID_CONF)
        host_id = config.get('hostagent','host_id')
    except Exception:
        log.exception("Error parsing host id from {0}. Skipping cleanup and continuing to start hostagent.".format(HOSTID_CONF))
        return
    desired_apps = os.path.join('/var/opt/pf9/hostagent', host_id, 'desired_apps.json')
    if not (os.path.isfile(desired_apps) and os.path.isdir('/var/cache/pf9apps')):
        return
    json_file = None
    try:
        json_file = open(desired_apps)
    except Exception:
        log.exception("Error reading contents from {0}. Skipping cleanup and continuing to start hostagent.".format(desired_apps))
        return
    try:
        data = json.load(json_file)
    except Exception:
        log.exception("Error loading file {0}. Skipping cleanup and continuing to start hostagent.".format(desired_apps))
        return
    finally:
        json_file.close()
    packages = os.listdir('/var/cache/pf9apps')
    for package in data:
        if package not in packages:
            continue
        version = data[package]['version']
        pkg_cache_dir = os.path.join('/var/cache/pf9apps', package)
        package_versions = os.listdir(pkg_cache_dir)
        for dir in package_versions:
            if version == dir:
                continue
            dir_to_delete = os.path.join(pkg_cache_dir, dir)
            try:
                log.info('Deleting package {0} version {1}'.format(package, dir))
                shutil.rmtree(dir_to_delete)
            except Exception:
                log.exception("Error removing the cached package file. Skipping cleanup of %s" % dir_to_delete) 
