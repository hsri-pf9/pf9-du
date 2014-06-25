#!/usr/bin/python

# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights reserved

# This script:
# + stops the resource manager and all the chkconfig'd openstack services,
# + creates new databases at the admin endpoint for each service
# + wires the new database into the service configs
# + creates new nova, keystone and glance databases, and migrates all the data from
#   the local mysql to the new databases.
# + restarts all the services.
#
# Requires the following environment variables:
# DBENDPOINT - admin endpoint of the mysql database, like
#              mysql://user:pass@host:port

import os
import logging
import re
import subprocess
import sys

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M')
log = logging.getLogger('db-setup')

class DbSetup(object) :

    # openstack services that are chkconfig'd on by packstack + resmgr
    services = ['openstack-glance-api',
                'openstack-glance-registry',
                'openstack-keystone',
                'openstack-nova-api',
                'openstack-nova-cert',
                'openstack-nova-conductor',
                'openstack-nova-consoleauth',
                'openstack-nova-network',
                'openstack-nova-novncproxy',
                'openstack-nova-scheduler',
                'pf9-resmgr']

    def __init__(self, admin_endpoint) :
        pattern = r'mysql://([^:]+):([^/]+)@([^:$]+)(?::(\d+))?'
        matches = re.match(pattern, admin_endpoint)
        if not matches or len(matches.groups()) < 4 :
            raise ValueError(
                'The DBENDPOINT was not of the form mysql://user:pass@host[:port].')
        self._user = matches.groups()[0]
        self._passwd = matches.groups()[1]
        self._host = matches.groups()[2]
        if matches.groups()[3] :
            self._port = int(matches.groups()[3])  # may raise ValueError
            log.info("Initiating database customization for {0}@{1}:{2}".format(
                self._user, self._host, self._port))
        else :
            self._port = None
            log.info("Initiating database customization for {0}@{1}".format(
                self._user, self._host))

    def stop_service(self, service_name) :
        try :
            subprocess.check_call(['service', service_name, 'stop'])
        except Exception as e :
            # not fatal
            log.warn("service %s stop raised %s" % (service_name, e))

    def stop_services(self) :
        """ Stop the openstack services. """
        log.info("stopping services...")
        for svc in DbSetup.services :
            self.stop_service(svc)

    def restart_services(self) :
        """ Restart the openstack services, raise exception on failure. """
        log.info("restarting services...")
        for svc in DbSetup.services :
            subprocess.check_call(['service', svc, 'restart'])

    def create_db(self, db_name) :
        """
        Create a database named db_name. The target database will be dropped
        if it exists.
        """
        log.info('creating %s database on %s' % (db_name, self._host))

        # add the password when we execute
        create_query = (
            "DROP DATABASE IF EXISTS {0}; " +
            "CREATE DATABASE {0}; " +
            "GRANT ALL PRIVILEGES on {0}.* TO '{0}' IDENTIFIED BY '{{0}}';"
            ).format(db_name)

        log.debug("Executing " + create_query.format("*****"))

        # FIXME - should we use different passwords for each db? If so, they'd need to
        # be generated and persisted externally so we can deal with upgrade.
        create_cmd = ['mysql', '-h' + self._host, '-u' + self._user,
                '-p' + self._passwd, '-e', create_query.format(self._passwd)]
        subprocess.check_call(create_cmd)

    def migrate_db(self, db_name) :
        """
        Migrates db_name from a local mysql instance (with no authentication) to a
        database with the same name at self._host.
        """
        log.info('migrating %s database to %s' % (db_name, self._host))
        dump_proc = subprocess.Popen(['mysqldump', db_name],
                                     stdout = subprocess.PIPE)
        load_proc = subprocess.Popen(['mysql', '-h' + self._host, '-u' + self._user,
                '-p' + self._passwd, db_name], stdin = dump_proc.stdout)
        dump_proc.stdout.close()
        load_proc.communicate()
        if 0 != load_proc.wait() :
            raise subprocess.CalledProcessError(
                    "Failed to load database data for" % db_name)
        if 0 != dump_proc.wait() :
            raise subprocess.CalledProcessError(
                    "Failed to dump database data for" % db_name)

    def config_dbs_in_services(self) :
        log.info("adding connection strings to configs")
        portstr = ':%s' % self._port if self._port else ''
        conn_template = 'mysql://{{0}}:{0}@{1}{2}/{{0}}'.format(
                self._passwd, self._host, portstr)
        subprocess.check_call(['openstack-config', '--set', '/etc/pf9/resmgr.conf',
                'database', 'sqlconnecturi', conn_template.format('resmgr')])
        subprocess.check_call(['openstack-config', '--set', '/etc/keystone/keystone.conf',
                'sql', 'connection', conn_template.format('keystone')])
        subprocess.check_call(['openstack-config', '--set', '/etc/nova/nova.conf',
                'DEFAULT', 'sql_connection', conn_template.format('nova')])
        subprocess.check_call(['openstack-config', '--set', '/etc/glance/glance-api.conf',
                'DEFAULT', 'sql_connection', conn_template.format('glance')])
        subprocess.check_call(['openstack-config', '--set', '/etc/glance/glance-registry.conf',
                'DEFAULT', 'sql_connection', conn_template.format('glance')])

if __name__ == '__main__' :
    # FIXME JIRA IAAS-519
    # Other services may be starting in between the stop and restart calls here
    # which could lead to incorrect config files and openstack-nova could be
    # confused about which database to use.

    # DBENDPOINT and thus db-setup is optional - only necessary for rds
    admin_endpoint = os.getenv('DBENDPOINT')
    if not admin_endpoint :
        log.warning('The DBENDPOINT environment variable was not provided. '
                  + 'Skipping db setup.')
        sys.exit(0)
    try :
        setup = DbSetup(admin_endpoint)
        setup.stop_services()
        for db in ['nova', 'glance', 'keystone'] :
            setup.create_db(db)
            setup.migrate_db(db)
        setup.create_db('resmgr')
        setup.config_dbs_in_services()
        setup.restart_services()
        setup.stop_service('mysqld')
        # FIXME - uninstall mysqld?
        sys.exit(0)
    except Exception as e :
        log.error("failed database setup: %s" % e)
        sys.exit(1)

