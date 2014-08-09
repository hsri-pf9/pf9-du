# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'Platform9'

from contextlib import contextmanager
import datetime
import glob
import logging
import json
import os
import dict_tokens

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

    def _setup_config(self, config):
        """
        Sets up the configuration data for a role
        :param dict config: config structure as a JSON object
        :return: Configuration data after value substitutions
        :rtype: str
        """

        # The params that can be substituted in a config string can either be
        # (1) part of the environment variables for the DU
        # (2) part of a predefined set of name, values.
        config_str = json.dumps(config)
        os_vars = os.environ

        # TODO: Make this dynamic. May be read in from some file?
        # Note: host_id becomes __HOST_ID__ token in the DB.
        #       At run-time, it gets replaced with each host's ID
        param_vals = {
            'du_fqdn': self.config.get("DEFAULT", "DU_FQDN"),
            'imglib_auth_user': self.config.get("pf9-imagelibrary", 'auth_user'),
            'imglib_auth_pass': self.config.get("pf9-imagelibrary", 'auth_pass'),
            'imglib_auth_tenant_name': self.config.get("pf9-imagelibrary",
                'auth_tenant_name'),
            'host_id': dict_tokens.HOST_ID_TOKEN
        }
        os_vars.update(param_vals)
        out = config_str % os_vars
        return out

    def _load_roles_from_files(self):
        """
        Read the roles related JSON metadata files and collate the role metadata
        information
        :return: The metadata of all the roles.
        :rtype: dict
        """
        metadata = {}
        file_pattern = '%s/*/*/*.json' % self.config.get('resmgr',
                                                         'role_metadata_location')
        for file in glob.glob(file_pattern):
            with open(file) as fp:
                try:
                    # Each file should represent data for one version of a role
                    data = json.load(fp)
                    if not isinstance(data, dict):
                        # Skip this metadata file and move on to the next file
                        log.error('Invalid role metadata file %s, data is not '
                                  'of expected dict format. Ignoring it', file)
                        continue
                    role_name = data['role_name']
                    role_version = data['config']['version']
                    log.info('Reading role data for %s, version %s',
                             role_name, data['config']['version'])
                    if not role_name in metadata:
                        metadata[role_name] = {
                            role_version: data
                        }
                    else:
                        metadata[role_name][role_version] = data
                except:
                    log.exception('Error loading the role metadata file %s', file)
                    # Skip this metadata file and continue
                    continue
        return metadata

    def setup_roles(self):
        """
        Pushes the roles related metadata into the database.
        """
        log.info('Setting up roles in the database')
        discovered_roles = self._load_roles_from_files()

        for role, role_info in discovered_roles.iteritems():
            for version, version_details in role_info.items():
                self.save_role_in_db(role, version, version_details)

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

        max_tries = 4
        for attempt in range(max_tries):
            try:
                with self.dbsession() as session:
                    try:
                        log.info('Adding/updating host %s', host_id)
                        session.merge(new_host)
                    except:
                        # log and raise
                        log.exception('Host %s update in database failed', host_id)
                        raise

                # Commit was successful (session went out of scope successfully)
                break
            except IntegrityError as e:
                log.exception('Host add/update failed')

                if e.orig[0] != 1062 or attempt ==  max_tries - 1:
                    # In case of key constraint violation (in this case only
                    # host id), the orig tuple of the exception has code 1062.
                    # Try to merge and commit again till max tries. Otherwise, raise
                    raise
            except:
                log.exception('Host add/update failed')
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

    def save_role_in_db(self, name, version, details):
        """
        Insert or update a role in the database. If the role already exists in
        database, an update is performed. Otherwise, the new role is inserted
        into the database.
        Also, this role version is marked as active and all other versions of
        the same role are marked as inactive in the DB.
        :param str name: Name of the role
        :param str version: Version of the role
        :param dict details: Details of role
        """
        role_id = '%s_%s' % (name, version)
        new_role = Role(id=role_id,
                        rolename=name,
                        version=version,
                        displayname=details['display_name'],
                        description=details['description'],
                        desiredconfig=self._setup_config(details['config']),
                        active=True)

        with self.dbsession() as session:
            try:
                result = session.query(Role).filter_by(rolename=name).all()
                if result:
                    # There are potentially other versions of the role in the DB
                    for role in result:
                        if role.version != version:
                            # Role in DB which is not in the metadata file now,
                            # tag such as inactive.
                            role.active = False
                # It is a new role which doesn't exist in the DB or
                # It is a role in the DB but is same as that of the version
                # to be considered active
                session.merge(new_role)
            except:
                log.exception('Role %s update in the database failed', role_id)
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
                    result = session.query(Role).filter_by(rolename=role_name).all()
            except NoResultFound:
                log.exception('No role found %s')
                result = None

        return result

    def _build_host_attributes(self, host_details, fetch_role_ids):
        """
        Internal utility method that builds a host dict object
        :param list roles: list of all roles for the host
        :param Host host_details: Host ORM object that contains the host information
        :param bool fetch_role_ids: Boolean to return role ids instead of role names
        :return: dictionary of host attributes
        :rtype: dict
        """
        roles = []
        if fetch_role_ids:
           for role in host_details.roles:
               roles.append(role.id)
        else:
            for role in host_details.roles:
                roles.append(role.rolename)

        host_attrs = {
            'id': host_details.id,
            'roles': roles,
            'info' : {
                'hostname': host_details.hostname,
                'os_family': host_details.hostosfamily,
                'arch': host_details.hostarch,
                'os_info': host_details.hostosinfo,
                'responding' : host_details.responding,
                'last_response_time' : host_details.lastresponsetime
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

    def query_host(self, host_id, fetch_role_ids=False):
        """
        Query the attributes for a particular host
        :param str host_id: ID of the host
        :param bool fetch_role_ids: Boolean to return role ids instead of role names
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
                    out = self._build_host_attributes(result, fetch_role_ids)
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
                out.append(self._build_host_attributes(host, fetch_role_ids=False))

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
                # Remove any previous association between that host and
                # the role name being associated here
                host.roles = set([r for r in host.roles if r.rolename != role_name])
                # Add the new role to that host
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

