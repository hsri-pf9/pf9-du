# Copyright 2015 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'Platform9'

import ConfigParser
import copy
import datetime
import dict_tokens
import dict_subst
import glob
import json
import logging
import random
import os
import string
import threading
import time

from contextlib import contextmanager
from exceptions import HostNotFound, HostConfigFailed, RoleNotFound
from sqlalchemy import create_engine, Column, String, Text, ForeignKey, Table
from sqlalchemy import Boolean, DateTime, UniqueConstraint, types
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, backref
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import IntegrityError


log = logging.getLogger('resmgr')

"""
This file deals with all the DB handling for Resource Manager. It leverages
sqlalchemy python module for all DB interactions.
"""
#Globals
Base = declarative_base()
engineHandle = None
_host_lock = threading.Lock()

# Maps roles to apps according the role metadata
role_app_map = {}

class JsonBlob(types.TypeDecorator):
    """ SQLAlchemy custom data type for JSON objects. Saves JSON as a string and
    retrieves it as a JSON object
    """
    impl = Text

    def process_bind_param(self, value, dialect):
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        return json.loads(value)


# Association table between hosts and roles
role_host_assoc_table = Table('host_role_map', Base.metadata,
                                  Column('res_id', String(50),
                                         ForeignKey('hosts.id')),
                                  Column('rolename', String(120),
                                         ForeignKey('roles.id')))

class RabbitCredential(Base):
    __tablename__ = 'rabbit_credentials'

    host_id = Column(String(50), ForeignKey('hosts.id'), primary_key=True)
    rolename = Column(String(120), ForeignKey('roles.rolename'), primary_key=True)
    userid = Column(String(60))
    password = Column(String(50))

class Role(Base):
    """The ORM class for the roles table in the database."""
    __tablename__ = 'roles'

    # id is currently assumed to be a concatenation of rolename_version
    id = Column(String(120), primary_key=True)
    rolename = Column(String(60))
    version = Column(String(60))
    displayname = Column(String(60))
    description = Column(String(256))
    desiredconfig = Column(JsonBlob())
    active = Column(Boolean()) # indicates if this is the active version of the role
    customizable_settings = Column(JsonBlob())
    rabbit_permissions = Column(JsonBlob())
    UniqueConstraint('rolename', 'version', name='constraint1')

    def __repr__(self):
        return "<Role(id = '%s', rolename='%s',version='%s',displayname='%s'," \
               "description='%s',desiredconfig='%s', active='%s', " \
               "customizable_settings='%s', rabbit_permissions='%s')>" % \
                (self.id, self.rolename, self.version, self.displayname,
                 self.description, self.desiredconfig, self.active,
                 self.customizable_settings, self.rabbit_permissions)


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
    role_settings = Column(JsonBlob())
    roles = relationship("Role", secondary=role_host_assoc_table,
                         backref='hosts', collection_class=set)
    rabbit_credentials = relationship('RabbitCredential',
                                      cascade='all, delete, delete-orphan')

    def __repr__(self):
        return "<Host(id='%s', hostname='%s', hostosfamily='%s', hostarch='%s', " \
               "hostosinfo='%s, lastresponsetime='%s', responding='%s', role_settings='%s')>" %\
               (self.id, self.hostname, self.hostosfamily, self.hostarch,
                self.hostosinfo, self.lastresponsetime, self.responding,
                self.role_settings)

class Service(Base):
    """ ORM class for service_configs table"""
    __tablename__ = 'service_configs'

    service_name = Column(String(512), primary_key=True)
    config_script_path = Column(String(512))
    settings = Column(JsonBlob())

    def to_dict(self):
        """ Converts a row to a dict object"""
        d = dict()
        for attr in self.__table__.columns:
            d[attr.name] = getattr(self, attr.name)

        return d

    def __repr__(self):
        return "<Service(service_name='%s', config_script_path='%s', settings='%s')>" %\
                (self.service_name, self.config_script_path, self.settings)


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
        # Populate/Update the roles table, if needed.
        log.info('Setting up roles in the database')
        self.setup_roles()
        self.setup_service_config()

    def _setup_config(self, config):
        """
        Sets up the configuration data for a role
        :param dict config: config structure as a JSON object
        :return: Configuration data after value substitutions
        :rtype: dict
        """

        # The params that can be substituted in a config string can either be
        # (1) part of the environment variables for the DU
        # (2) part of a predefined set of name, values.
        config_str = json.dumps(config)
        os_vars = os.environ

        # TODO: Make this dynamic. May be read in from some file?
        # Note: host_id becomes __HOST_ID__ token in the DB.
        #       At run-time, it gets replaced with each host's ID
        du_fqdn = self.config.get("DEFAULT", "DU_FQDN")

        param_vals = {
            'du_fqdn': du_fqdn,
            'imglib_auth_user': self.config.get("pf9-imagelibrary", 'auth_user'),
            'imglib_auth_pass': self.config.get("pf9-imagelibrary", 'auth_pass'),
            'imglib_auth_tenant_name': self.config.get("pf9-imagelibrary",
                'auth_tenant_name'),
            'cinder_auth_user': self.config.get("pf9-cindervolume", 'auth_user'),
            'cinder_auth_pass': self.config.get("pf9-cindervolume", 'auth_pass'),
            'cinder_db_pass': self.config.get("pf9-cindervolume", 'db_pass'),
            'cinder_auth_tenant_name': self.config.get("pf9-cindervolume",
                'auth_tenant_name'),
            'host_id': dict_tokens.HOST_ID_TOKEN,
            'host_relative_amqp_fqdn': dict_tokens.HOST_RELATIVE_AMQP_FQDN_TOKEN,
            'download_protocol': dict_tokens.DOWNLOAD_PROTOCOL,
            'download_port': dict_tokens.DOWNLOAD_PORT,
            'rabbit_userid' : dict_tokens.RABBIT_USERID_TOKEN,
            'rabbit_password' : dict_tokens.RABBIT_PASSWORD_TOKEN
        }
        param_vals['ceilometer_auth_user'] = self.config.get("pf9-ceilometer", 'auth_user')
        param_vals['ceilometer_auth_pass'] = self.config.get("pf9-ceilometer", 'auth_pass')
        param_vals['ceilometer_auth_tenant_name'] = self.config.get("pf9-ceilometer",
            'auth_tenant_name')
        os_vars.update(param_vals)
        os_vars.update(self._flat_config())
        out = config_str % os_vars
        return json.loads(out)

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
                    role_version = data['role_version']
                    log.info('Reading role data for %s, version %s',
                             role_name, role_version)
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

    def setup_service_config(self):
        """
        Update service config settings based on metadata on the filesystem.
        """
        log.info('Setting up service config in the database')
        file_pattern = '/etc/pf9/resmgr_svc_configs/*.json'

        for f in glob.glob(file_pattern):
            with open(f) as fp:
                try:
                    data = json.load(fp)
                    for svc, details in data.iteritems():
                        svc_db = self.query_service_config(svc)
                        settings = svc_db['settings'] if svc_db else details['settings']
                        self.set_service_config(svc, details['path'], settings)
                except:
                    log.exception('Error loading the service config file %s', f)
                    continue


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

    def get_custom_settings(self, host_id, role_name):
        """
        Gets the custom config stored in customized_config column in hosts
        table. If the host does not exist, returns the default settings
        for the specified role.
        """
        with self.dbsession() as session:
            try:
                host = session.query(Host).filter_by(id=host_id).first()
                if host:
                    role_settings = host.role_settings
                    if role_name not in role_settings:
                        log.error('Host %s does not have role %s', host_id, role_name)
                        raise RoleNotFound(role_name)
                    return role_settings[role_name]
                else:
                    log.error('Host %s is not a recognized host', host_id)
                    raise HostNotFound(host_id)
            except Exception as ex:
                log.exception('DB exception [%s] while getting customized config for %s'
                              ' host and role %s', ex, host_id, role_name)
                raise

    def _get_default_settings(self, role_name):
        """
        Requires that the role exists in the database.
        """
        role = self.query_role(role_name)
        default_settings = {}
        for default_setting_name, default_setting in role.customizable_settings.iteritems():
                default_settings[default_setting_name] = default_setting['default']
        return default_settings


    def _update_settings_with_defaults(self, settings, default_settings, role_name):
        """
        Update with defaults if they were not overwritten
        """
        for key, val in default_settings.iteritems():
            if key not in settings[role_name]:
                settings[role_name][key] = val

    def insert_update_host(self, host_id, host_details, role_name, settings_to_add):
        """
        Add a new host into the database or update the entries for an
        existing host in the database. The host details passed is a
        dictionary of host details. It should contain hostname, os_family,
        arch, os_info.
        :param str host_id: ID of the host to be added
        :param dict host_details: Dictionary of the host details that
         needs to be added.
        :param dict settings_to_add: The json body of the request.
            If this is None, the host will use all of the default settings
        """
        max_tries = 4
        for attempt in range(max_tries):
            try:
                with _host_lock:
                    with self.dbsession() as session:
                        host = session.query(Host).filter_by(id=host_id).first()
                        default_settings = self._get_default_settings(role_name)

                        if not set(settings_to_add).issubset(set(default_settings)):
                            invalid_keys = set(settings_to_add) - set(default_settings)
                            raise HostConfigFailed('Invalid keys in body %s' % invalid_keys)

                        if host:
                            # Update the existing custom settings
                            # with the specified custom settings
                            # NOTE: role_settings is managed as a custom
                            # datatype in SQLAlchemy. This makes the property
                            # non mutable. deepcopy is needed to update
                            # role_settings.
                            settings = copy.deepcopy(host.role_settings)
                            if role_name not in settings:
                                settings[role_name] = {}
                            settings[role_name].update(settings_to_add)
                        else:
                            settings = {role_name : settings_to_add}
                        self._update_settings_with_defaults(settings, default_settings, role_name)

                        new_host = Host(id=host_id,
                                        hostname=host_details['hostname'],
                                        hostosfamily=host_details['os_family'],
                                        hostarch=host_details['arch'],
                                        hostosinfo=host_details['os_info'],
                                        responding=True,
                                        role_settings=settings)
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
                host = session.query(Host).filter_by(id=host_id).first()
                if responding:
                    log.info('Marking the host %s(%s) as responding', host.hostname, host_id)
                    host.lastresponsetime = None
                    host.responding = True
                else:
                    log.info('Marking the host %s(%s) as not responding', host.hostname, host_id)
                    host.lastresponsetime = datetime.datetime.utcnow()
                    host.responding = False
            except:
                log.exception('Marking host %s as %s responding failed',
                              host_id, '' if responding else 'not')
                raise

    def update_host_hostname(self, host_id, hostname):
        """
        Update the host entry in the database with the specified hostname
        """
        with self.dbsession() as session:
            try:
                host = session.query(Host).filter_by(id=host_id).first()
                host.hostname = hostname
            except:
                log.exception('Failed to update host %s with hostname %s'
                              % (host_id, hostname))
                raise
        log.info('hostname for %s has changed to %s' % (host_id, hostname))

    def save_role_in_db(self, name, version, details):
        """
        Insert or update a role in the database. If the role already exists in
        database, an update is performed. Otherwise, the new role is inserted
        into the database.
        Also, this role version is marked as active and all other versions of
        the same role are marked as inactive in the DB.
        Also, updates the role_app_map.
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
                        active=True,
                        customizable_settings=details['customizable_settings'],
                        rabbit_permissions=details['rabbit_permissions'])

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
        role_app_map[name] = set(details['config'].keys())

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

    def query_roles_for_host(self, host_id):
        """
        Query the role details assigned to the particular host
        :param str host_id: ID of the host
        :return: List of role objects for the host. None if the
        host is not present
        :rtype: List of roles
        """
        log.info('Querying roles for host %s', host_id)
        out = None
        with self.dbsession() as session:
            try:
                result = session.query(Host).filter_by(id=host_id).first()
                if result:
                    out = list(result.roles)
            except NoResultFound:
                log.exception('No host found %s', host_id)

        return out

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

    def query_rabbit_credentials(self, **filter_kwargs):
        with self.dbsession() as session:
            return session.query(RabbitCredential).filter_by(**filter_kwargs).all()

    def query_host_and_app_details(self, host_id=None):
        """
        Query host details and returns a JSON serializable dictionary and not
        the ORM object. Use this to reference the host data beyond the database
        session. If host_id is not provided, all hosts are queried.
        :param str host_id: ID of the host.
        :return: list of hosts' properties in JSON format
        :rtype: dict
        """
        log.info('Querying host details for %s', host_id if host_id else 'all hosts')
        out = {}
        results = None
        with self.dbsession() as session:
            if host_id:
                try:
                    results = [session.query(Host).filter_by(id=host_id).first()]
                except NoResultFound:
                    log.exception('No host found for id %s', host_id)
            else:
                results = session.query(Host).all()
            for host in results:
                assigned_apps = {}
                for role in host.roles:
                    assigned_apps.update(role.desiredconfig)

                out[host.id] = {
                    'hostname': host.hostname,
                    'hostosfamily': host.hostosfamily,
                    'hostarch': host.hostarch,
                    'hostosinfo': host.hostosinfo,
                    'lastresponsetime': host.lastresponsetime,
                    'responding': host.responding,
                    'apps_config': assigned_apps,
                    'role_settings': host.role_settings
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

    def associate_rabbit_credentials_to_host(self,
                                             host_id,
                                             role_name,
                                             rabbit_user,
                                             rabbit_password):
        """
        Associate rabbitmq_credentials to the host.
        :param str host_id: ID of the host
        :param str role_name: role.rolename of the role
        """
        log.info('Associating rabbit credentials to role %s and host %s',
                 role_name, host_id)
        with self.dbsession() as session:
            try:
                host = session.query(Host).filter_by(id=host_id).first()
                roles_with_credentials = set(rabbit_credential.rolename
                                             for rabbit_credential in host.rabbit_credentials)
                if role_name in roles_with_credentials:
                    # The host already has rabbit credentials for the specified role
                    log.warn('Host %s already has rabbit credentials for role %s'
                             % (host_id, role_name))
                    return
                credential = RabbitCredential(rolename=role_name,
                                              userid=rabbit_user,
                                              password=rabbit_password)
                host.rabbit_credentials.append(credential)
            except:
                log.exception('DB error while associating rabbit credentials to host %s',
                              host_id)
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
                for role in host.roles:
                    if role.rolename == role_name:
                        host.roles.remove(role)
                        break
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


    def substitute_rabbit_credentials(self, dictionary, host_id):
        """
        Replaces Rabbit credential tokens in a dictionary with actual credentials
        """
        def app_to_role():
            """
            Return the role that is in the token_role_map, and
            provides the specified app.
            Assumes that no host will have two roles that provide the same app.
            """
            for role, apps in role_app_map.iteritems():
                if app in apps and role in token_role_map:
                    return role

        with self.dbsession() as session:
            host = session.query(Host).filter_by(id=host_id).first()
            # Maps roles to token maps
            token_role_map = {}
            for credential in host.rabbit_credentials:
                token_role_map[credential.rolename] = {dict_tokens.RABBIT_USERID_TOKEN : credential.userid,
                                                       dict_tokens.RABBIT_PASSWORD_TOKEN : credential.password}

        for app in dictionary:
            # The role that provides the app
            role = app_to_role()
            if role not in token_role_map:
                log.error('Did not find rabbit credentials for role %s' % role)
                continue
            dictionary[app] = dict_subst.substitute(dictionary[app], token_role_map[role])

    def _flat_config(self):
        ret = {}
        for item in self.config.defaults().iteritems():
            ret['DEFAULT.%s' % item[0]] = item[1]
        for section in self.config.sections():
            for item in self.config.items(section):
                ret['%s.%s' % (section, item[0])] = item[1]
        return ret

    def set_service_config(self, service_name, config_script_path, settings):
        """
        Update all service properties for a service
        """
        log.info('Setting config settings for service %s', service_name)
        with self.dbsession() as session:
            try:
                new_svc = Service(service_name=service_name,
                                  config_script_path=config_script_path,
                                  settings=settings)
                session.merge(new_svc)
            except:
                log.exception('DB error while updating service %s', service_name)
                raise

    def update_service_settings(self, service_name, settings):
        """
        Update the settings for a particular service
        """
        log.info('Setting config settings for service %s', service_name)
        with self.dbsession() as session:
            try:
                svc = session.query(Service).filter_by(service_name=service_name).first()
                svc.settings = settings
            except:
                log.exception('DB error while updating settings for service %s',
                              service_name)
                raise

    def query_service_config(self, service_name):
        """Query a single service's config details"""
        log.info('Querying service_name %s settings', service_name)
        with self.dbsession() as session:
            results = session.query(Service).filter_by(service_name=service_name).first()

        return results.to_dict() if results else {}

    def get_service_configs(self):
        """Query all the service config details"""
        log.info('Querying all service configs')
        out = []
        with self.dbsession() as session:
            results = session.query(Service).all()

        for r in results:
            out.append(r.to_dict())

        return out
