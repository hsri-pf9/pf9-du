# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'Platform9'

from contextlib import contextmanager
import datetime
import logging
import json

from exceptions import HostNotFound

from sqlalchemy import create_engine, Column, String, ForeignKey, Table
from sqlalchemy import Boolean, DateTime, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, backref
from sqlalchemy.orm.exc import NoResultFound


log = logging.getLogger('resmgr')

"""
This file deals with all the DB handling for Resource Manager. It leverages
sqlalchemy python module for all DB interactions.
"""
#Globals
Base = declarative_base()
engineHandle = None

# Association table between hosts and roles
role_host_assoc_table = Table('host_role_map', Base.metadata,
                                  Column('res_id', String(50),
                                         ForeignKey('hosts.id')),
                                  Column('rolename', String(120),
                                         ForeignKey('roles.id')))

#TODO: Move this to a configuration file?
_roles = {
    'pf9-ostackhost': {
        'display_name': 'Openstack host',
        'description': 'Host assigned to run OpenStack Software',
        'active': True,
        'config': {
            'version': '1.0.0-1',
            'running': True,
            'url': 'https://%(du_host)s/ostackhost/pf9-ostackhost-1.0.0-1'
                   '.x86_64.rpm',
            'config': {
                'nova': {
                    'DEFAULT': {
                        'rabbit_host': '%(du_host)s',
                        'ec2_dmz_host': '%(du_host)s',
                        'glance_api_servers': '%(du_host)s:9292',
                        'rabbit_password': '%(ostack_password)s',
                        'xvpvncproxy_base_url':
                            'http://%(du_host)s:6081/console',
                        's3_host': '%(du_host)s',
                        'flat_interface': '%(interface)s',
                        'novncproxy_base_url':
                            'http://%(du_host)s:6080/vnc_auto.html'
                    },
                    'spice': {
                        'html5proxy_base_url':
                            'http://%(du_host)s:6082/spice_auto.html'
                    }
                },
                'api-paste': {
                    'filter:authtoken': {
                        'admin_password': '%(ostack_password)s',
                        'auth_host': '%(du_host)s'
                    }
                }
            }
        }
    }
}

class Role(Base):
    """The ORM class for the roles table in the database."""
    __tablename__ = 'roles'

    # id is currently assumed to be a concatenation of rolename_version
    id = Column(String(120), primary_key=True)
    rolename = Column(String(60))
    version = Column(String(60))
    displayname = Column(String(60))
    description = Column(String(256))
    desiredconfig = Column(String(2048))
    active = Column(Boolean()) # indicates if this is the active version of the role
    UniqueConstraint('rolename', 'version', name='constraint1')

    def __repr__(self):
        return "<Role(id = '%s', rolename='%s',version='%s',displayname='%s'," \
               "description='%s',desiredconfig='%s', active='%s')>" % \
                (self.id, self.rolename, self.version, self.displayname,
                 self.description, self.desiredconfig, self.active)


class Host(Base):
    """The ORM class for the hosts table in the database."""
    __tablename__ = 'hosts'

    id = Column(String(50), primary_key=True)
    hostname = Column(String(256))
    hostosfamily = Column(String(256))
    hostarch = Column(String(50))
    hostosinfo = Column(String(256))
    lastresponsetime = Column(DateTime(), default=None) # timestamp when last status was recorded
    responding = Column(Boolean)
    roles = relationship("Role", secondary=role_host_assoc_table,
                         backref='hosts', collection_class=set)

    def __repr__(self):
        return "<Host(id='%s', hostname='%s', hostosfamily='%s', hostarch='%s', " \
               "hostosinfo='%s, lastresponsetime='%s', responding='%s')>" %\
               (self.id, self.hostname, self.hostosfamily, self.hostarch,
                self.hostosinfo, self.lastresponsetime, self.responding)


class ResMgrDB(object):
    """
    Provides abstraction over the ORM classes. Provides DB functionality relating
    to the resource manager.
    """
    def __init__(self, config):
        """
        Constructor
        :param ConfigParser config: config object for resmgr
        """
        self.config = config
        self.connectstr = config.get('database', 'sqlconnectURI')
        self.session_maker = sessionmaker(bind=self.dbengine)
        self._init_db()

    def _init_db(self):
        """
        Initializes the database tables for Resource Manager
        """
        log.info('Setting up the database for resource manager')
        Base.metadata.create_all(self.dbengine)
        # Populate/Update the roles table, if needed.
        self.setup_roles()

    def _setup_config(self, role, config):
        """
        Sets up the configuration data for a role
        :param str role: role name
        :param dict config: config structure as a JSON object
        :return: Configuration data after value substitutions
        :rtype: str
        """
        out = None
        config_str = json.dumps(config)
        # Currently, only ostackhost config is supported
        if role == 'pf9-ostackhost':
            param_vals = {
                'du_host': self.config.get("DEFAULT", "DU_FQDN"),
                'interface': "eth0",
                'ostack_password': "m1llenn1umFalc0n",
            }
            out = config_str % param_vals

        return out

    def setup_roles(self):
        """
        Pushes the roles related metadata into the database.
        """
        log.info('Setting up roles in the database')
        for k, v in _roles.iteritems():
            config_str = self._setup_config(k, v['config'])
            version = v['config']['version']
            id = '%s_%s' % (k, version)
            self.insert_update_role(id, k, version, v['display_name'],
                                    v['description'], config_str, v['active'])

    @property
    def dbengine(self):
        """Get the database engine instance. If uninitialized, it will create one."""
        global engineHandle

        if not engineHandle:
            engineHandle = create_engine(self.connectstr)

        return engineHandle

    def _has_uncommitted_changes(self, session):
        """
        Method to check if a session has pending changes. Pending changes can
        be new, modified or deleted objects corresponding to the DB state.
        :param Session session: SQLAlchmey ORM session instance
        :return: True if there is a pending change, else False
        :rtype: bool
        """
        if session.dirty or session.new or session.deleted:
            # TODO: This is temporarily here for monitoring. To be removed
            log.debug('Session has pending changes %s %s %s',
                      session.dirty, session.deleted, session.new)
            return True
        return False

    @contextmanager
    def dbsession(self):
        """
        Get the database session instance to run database operations. Integrated
        with contextmanager and can be used with the 'with' statement.
        When the context goes out of scope, the session is committed if there are
        uncommitted changes (or rolled back in case of errors). The session is
        finally closed.
        """
        session = self.session_maker()
        try:
            yield session
            # TODO: This is temporarily here for monitoring. To be removed.
            log.info('Connection pool status: %s', self.dbengine.pool.status())
            if self._has_uncommitted_changes(session):
                session.commit()
        except:
            if self._has_uncommitted_changes(session):
                session.rollback()
            raise
        finally:
            session.close()

    def insert_update_host(self, host_id, host_details):
        """
        Add a new host into the database or update the entries for an
        existing host in the database. The host details passed is a
        dictionary of host details. It should contain hostname, os_family,
        arch, os_info.
        :param str host_id: ID of the host to be added
        :param dict host_details: Dictionary of the host details that
         needs to be added.
        """
        new_host = Host(id=host_id,
                        hostname=host_details['hostname'],
                        hostosfamily=host_details['os_family'],
                        hostarch=host_details['arch'],
                        hostosinfo=host_details['os_info'],
                        responding=True)

        with self.dbsession() as session:
            try:
                log.info('Adding/updating host %s', host_id)
                session.merge(new_host)
            except:
                # log and raise
                log.exception('Host %s update in database failed', host_id)
                raise

    def delete_host(self, host_id):
        """
        Removes a host entry from the database.
        :param str host_id: Host ID to be purged from the database.
        """
        with self.dbsession() as session:
            try:
                log.info('Deleting host %s from the database', host_id)
                del_host = session.query(Host).filter_by(id=host_id).first()
                session.delete(del_host)
            except NoResultFound:
                log.error('Could not find host %s in the database', host_id)
                raise HostNotFound(del_host)
            except:
                log.exception('Deleting host %s in the database failed', host_id)
                raise

    def mark_host_state(self, host_id, responding=False):
        """
        Tag a host as responding or not in the database. If being marked as
        not responding, the responding field is False and the 'lastresponsetime'
        field is updated with the current timestamp.
        :param str host_id: ID of the host to be marked
        :param bool responding: Indicate if the host is to be marked responding
        or not
        """
        with self.dbsession() as session:
            try:
                del_host = session.query(Host).filter_by(id=host_id).first()
                if responding:
                    log.info('Marking the host %s as responding', host_id)
                    del_host.lastresponsetime = None
                    del_host.responding = True
                else:
                    log.info('Marking the host %s as not responding', host_id)
                    del_host.lastresponsetime = datetime.datetime.utcnow()
                    del_host.responding = False
            except:
                log.exception('Marking host as %s responding failed',
                              '' if responding else 'not')
                raise

    def insert_update_role(self, id, role_name, version, display_name,
                           description, desired_config, active):
        """
        Insert or update a role in the database. If the role already exists in
        database, an update is performed. Otherwise, the new role is inserted
        into the database.
        :param str id: ID of the role
        :param str role_name: Name of the role
        :param str version: Version of the role
        :param str display_name: User friendly name of the role
        :param str description: Description of the role
        :param dict desired_config: Actual configuration or the configuration
        template of the role.
        :param bool active: Indicates if this is the active version of the role
        """
        new_role = Role(id=id,
                        rolename=role_name,
                        version=version,
                        displayname=display_name,
                        description=description,
                        desiredconfig=desired_config,
                        active=active)

        with self.dbsession() as session:
            try:
                log.info('Insert/updating role %s, active=%s', id, active)
                session.merge(new_role)
            except:
                log.exception('Role %s update in database failed', id)
                raise

    def query_role(self, role_name, active_only=True):
        """
        Query the attributes of a particular role from the database. If
        active_only is specified, then the only active version of the roles
        is returned.
        :param str role_name: ID of the role.
        :param bool active_only: If True, only active versions of the role are returned
        :return: Role object with the role attributes. None if role is not present
        :rtype: Role
        """
        log.info('Querying role %s, active only = %s', role_name, active_only)
        with self.dbsession() as session:
            try:
                if active_only:
                    result = session.query(Role).filter_by(rolename=role_name, active=True).first()
                else:
                    result = session.query(Role).filter_by(rolename=role_name).first()
            except NoResultFound:
                log.exception('No role found %s')
                result = None

        return result

    def _build_host_attributes(self, host_details):
        """
        Internal utility method that builds a host dict object
        :param list roles: list of all roles for the host
        :param Host host_details: Host ORM object that contains the host information
        :return: dictionary of host attributes
        :rtype: dict
        """
        roles = []
        for role in host_details.roles:
            roles.append(role.rolename)

        host_attrs = {
            'id': host_details.id,
            'roles': roles,
            'info' : {
                'hostname': host_details.hostname,
                'os_family': host_details.hostosfamily,
                'arch': host_details.hostarch,
                'os_info': host_details.hostosinfo
            }
        }
        return host_attrs

    def query_roles(self, active_only=True):
        """
        Queries all the roles present in the database. If active_only is specified,
        then the only active version of the roles is returned.
        :param bool active_only: If True, only active versions of the roles are returned
        :return: List of Role objects
        :rtype: list
        """
        log.info('Querying all roles, active only = %s', active_only)
        with self.dbsession() as session:
            if active_only:
                results = session.query(Role).filter_by(active=True).all()
            else:
                results = session.query(Role).all()

        return results

    def query_host(self, host_id):
        """
        Query the attributes for a particular host
        :param str host_id: ID of the host
        :return: Host object with the host attributes. None if the
        host is not present
        :rtype: Host
        """
        log.info('Querying host %s', host_id)
        out = None
        with self.dbsession() as session:
            try:
                result = session.query(Host).filter_by(id=host_id).first()
                if result:
                    out = self._build_host_attributes(result)
            except NoResultFound:
                log.exception('No host found %s', host_id)

        return out

    def query_hosts(self):
        """
        Query all the hosts in the database
        :return: list of host objects
        :rtype: list
        """
        log.info('Querying all hosts')
        out = []
        with self.dbsession() as session:
            results = session.query(Host).all()
            for host in results:
                out.append(self._build_host_attributes(host))

        return out

    def query_host_details(self):
        """
        Query all host details and returns a JSON serializable dictionary and not
        the ORM object. Use this to reference the host data beyond the database
        session
        :return: list of hosts' properties in JSON format
        :rtype: dict
        """
        log.info('Querying all hosts details')
        out = {}
        with self.dbsession() as session:
            results = session.query(Host).all()
            for host in results:
                assigned_roles = {}
                for role in host.roles:
                    assigned_roles[role.rolename] = json.loads(role.desiredconfig)

                out[host.id] = {
                    'hostname': host.hostname,
                    'hostosfamily': host.hostosfamily,
                    'hostarch': host.hostarch,
                    'hostosinfo': host.hostosinfo,
                    'lastresponsetime': host.lastresponsetime,
                    'responding': host.responding,
                    'roles_config': assigned_roles,
                    }

        return out


    def associate_role_to_host(self, host_id, role_name):
        """
        Associate a role to the host.
        :param str host_id: ID of the host
        :param str role_name: ID of the role
        """
        log.info('Adding role %s to host %s', role_name, host_id)
        with self.dbsession() as session:
            try:
                host = session.query(Host).filter_by(id=host_id).first()
                role = session.query(Role).filter_by(rolename=role_name,
                                                     active=True).first()
                host.roles.add(role)
            except:
                log.exception('DB error while associating host %s with role %s',
                              host_id, role_name)
                raise

    def remove_role_from_host(self, host_id, role_name):
        """
        Remove a role from a given host
        :param str host_id: ID of the host
        :param str role_name: ID of the role
        """
        log.info('Removing role %s from host %s', role_name, host_id)
        with self.dbsession() as session:
            try:
                host = session.query(Host).filter_by(id=host_id).first()
                role = session.query(Role).filter_by(rolename=role_name, active=True).first()
                host.roles.remove(role)
            except:
                log.exception('DB error while removing role %s from host %s',
                              role_name, host_id)
                raise

    def update_roles_for_host(self, host_id, roles):
        """
        Updates the roles associated with a particular host.
        :param str host_id: ID of the host
        :param list roles: list of role IDs to associated with the host.
        """
        log.info('Updating roles %s for host %s', roles, host_id)
        with self.dbsession() as session:
            try:
                host = session.query(Host).filter_by(id=host_id).first()
                roles_set = set(roles)
                host.roles = roles_set
            except:
                log.exception('DB error while updating roles %s for host %s',
                              roles, host_id)
                raise

