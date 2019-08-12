# Copyright 2015 Platform9 Systems Inc.
# All Rights Reserved.

# pylint: disable=too-few-public-methods,too-many-public-methods
# pylint: disable=bad-indentation,bare-except,no-else-return

__author__ = 'Platform9'

import copy
import datetime
import glob
import json
import logging
import os
import threading

from six.moves.configparser import ConfigParser
from six import iteritems
from contextlib import contextmanager
from sqlalchemy import create_engine, Column, String, Text, ForeignKey
from sqlalchemy import Boolean, DateTime, UniqueConstraint, types
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import IntegrityError

from resmgr import role_states
from resmgr.exceptions import HostNotFound, HostConfigFailed, RoleNotFound


log = logging.getLogger(__name__)

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
        # Deal with possible NULL values in the field
        # NOTE: This doesn't treat '' as a NULL field
        if value is None:
            return None

        return json.dumps(value)

    def process_result_value(self, value, dialect):
        # Deal with possible NULL values in the field
        if value is None:
            return None

        return json.loads(value)

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
    hosts = relationship('HostRoleAssociation', back_populates='role')
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
    rabbit_credentials = relationship('RabbitCredential',
                                      cascade='all, delete, delete-orphan')
    roles = relationship('HostRoleAssociation', back_populates='host')

    def __repr__(self):
        return "<Host(id='%s', hostname='%s', hostosfamily='%s', hostarch='%s', " \
               "hostosinfo='%s, lastresponsetime='%s', responding='%s', role_settings='%s')>" %\
               (self.id, self.hostname, self.hostosfamily, self.hostarch,
                self.hostosinfo, self.lastresponsetime, self.responding,
                self.role_settings)

class HostRoleAssociation(Base):
    """
    Relationship between a role and host.
    """
    __tablename__ = 'host_role_map'
    host_id = Column('res_id', String(50),
                     ForeignKey('hosts.id'), primary_key=True)
    # note that the column name is rolename, though it's actually the
    # role's id <name>_<version>. Use role_id in mapping to avoid confusion.
    role_id = Column('rolename', String(120),
                     ForeignKey('roles.id'), primary_key=True)
    current_state = Column('current_state', String(120))
    host = relationship('Host', back_populates='roles')
    role = relationship('Role', back_populates='hosts')
    __table_args__ = (UniqueConstraint('rolename', 'res_id'),)

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
        self.db_connection_options = {}

        # Override SQLAlchemy default pool size if defined
        if config.has_option('database', 'pool_size'):
            self.db_connection_options['pool_size'] = config.getint('database', 'pool_size')
        else:
            log.info('No database connection pool_size configured. '
                      'Using SQLAlchemy default pool_size.')


        """
        Checking pool_status is required since size() function
        if not defined for pool types like NullPool, StaticPool and
        AssertionPool.
        Save the threshold (15% of pool size) for remaining connections in the pool,
        which gets checked in dbsession() to make some decisions.
        """
        pool_status = self.dbengine.pool.status()
        if pool_status not in ['NullPool', 'StaticPool', 'AssertionPool']:
            self.pool_rem_conns_threshold = self.dbengine.pool.size() * (15.0/100)

        # Set Pessimistic disconnect handling
        if config.has_option('database', 'pessimistic_disconnect_handling'):
            self.db_connection_options['pool_pre_ping'] = config.getboolean('database',
                                                            'pessimistic_disconnect_handling')
        else:
            log.info('No pessimistic disconnect handling. Using SQLAlchemy default')

        self.session_maker = sessionmaker(bind=self.dbengine)
        # Populate/Update the roles table, if needed.
        log.info('Setting up roles in the database')
        self.setup_roles()
        self.setup_service_config()

    @staticmethod
    def _replace_legacy_tokens(app_config_str):
        """
        Previous versions of resource manager used string substitution with
        tokens like __HOST_ID__. These may still be in the role spec in the
        resource manager database. Replace them here with python format
        tokens.
        """
        legacy_tokens = {
            '__HOST_ID__': '%(host_id)s',
            '__RABBIT_USERID__': '%(rabbit_userid)s',
            '__RABBIT_PASSWORD__': '%(rabbit_password)s',
            '__RABBIT_TRANSPORT_URL__': '%(rabbit_transport_url)s',
            '__HOST_CONFIG__': '%(host_config)s'
        }

        for underscore_token, py_token in iteritems(legacy_tokens):
            app_config_str = app_config_str.replace(underscore_token, py_token)
        return app_config_str

    def _get_rabbit_credential_params(self, host_id, role_name):
        """
        Look up the rabbit credentials for (host, role) combination. If found
        return in a dictionary like
        {
            'rabbit_userid': 'exampleuser',
            'rabbit_password': 'examplepass',
            'rabbit_transport_url': \
                'rabbit://exampleuser:examplepass@localhost:5673/'
        }
        If not found return an empty dictionary.
        """
        with self.dbsession() as session:
            rows = session.query(RabbitCredential).filter_by(host_id=host_id,
                                                             rolename=role_name
                                                             ).all()
        if not rows:
            log.warn('No rabbit credentials exist for host %s, role %s.',
                     host_id, role_name)
            return {}
        elif len(rows) > 1:
            log.warn('Multiple rabbit credentials exist for host %s, role %s. '
                     'Choosing first entry', host_id, role_name)
        creds = rows[0]
        return {
            'rabbit_userid': creds.userid,
            'rabbit_password': creds.password,
            'rabbit_transport_url': 'rabbit://%s:%s@localhost:5673/' % \
                                    (creds.userid, creds.password)
        }

    def _flat_config(self):
        ret = {}
        for item in iteritems(self.config.defaults()):
            ret['DEFAULT.%s' % item[0]] = item[1]
        for section in self.config.sections():
            for item in self.config.items(section):
                ret['%s.%s' % (section, item[0])] = item[1]
        return ret

    def _substitute_host_role_params(self, host_id, rolename, app_specs):
        """
        Gather all the parameters that need to be plugged into a host role
        spec. This is used as a helper for query_host_and_app_details.
        Any future changes to substitution should stay here.
        """
        params = os.environ.copy()
        params.update(self._flat_config())
        params.update(self._get_rabbit_credential_params(host_id, rolename))
        params['host_id'] = host_id

        # These are replaced in hostagent
        params.update({
            'download_protocol': '%(download_protocol)s',
            'host_relative_amqp_fqdn': '%(host_relative_amqp_fqdn)s',
            'download_port': '%(download_port)s'
        })

        # this might show up as part of an endpoint spec
        params['project_id'] = '%(project_id)s'

        # this will be replaced with dict_subst when we call the auth
        # event
        params['host_config'] = '__HOST_CONFIG__'

        new_app_specs = {}
        for appname, config in iteritems(app_specs):
            config_string = json.dumps(config)
            config_string = self._replace_legacy_tokens(config_string)
            config_string = config_string % params
            new_app_specs[appname] = json.loads(config_string)

        return new_app_specs

    def _validate_role_config(self, role_spec):
        """
        Make sure that all the values needed to configure a role are available.
        Use dummy host_id and rabbit credentials (which won't be known until
        the role is actually applied to a host) and attempt to render the
        config. Raise a KeyError on failure. Run this before we load the role
        into the database.
        """
        params = os.environ.copy()
        params.update(self._flat_config())
        params.update({
            'rabbit_userid': 'dummy_user',
            'rabbit_password': 'dummy_password',
            'rabbit_transport_url': 'http://dummy:dummy@dummy'
        })
        params['host_id'] = 'dummy_hostid'
        params['host_config'] = 'dummy_host_config'

        # These are replaced in hostagent
        params.update({
            'download_protocol': '%(download_protocol)s',
            'host_relative_amqp_fqdn': '%(host_relative_amqp_fqdn)s',
            'download_port': '%(download_port)s'
        })

        # this might show up as part of an endpoint spec
        params['project_id'] = '%(project_id)s'

        # check it
        role_string = json.dumps(role_spec)
        role_string = self._replace_legacy_tokens(role_string)
        role_string % params

        # return if ok
        return role_spec

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
        for filename in glob.glob(file_pattern):
            with open(filename) as fp:
                try:
                    # Each file should represent data for one version of a role
                    data = json.load(fp)
                    if not isinstance(data, dict):
                        # Skip this metadata file and move on to the next file
                        log.error('Invalid role metadata file %s, data is not '
                                  'of expected dict format. Ignoring it', filename)
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
                    log.exception('Error loading the role metadata file %s', filename)
                    # Skip this metadata file and continue
                    continue
        return metadata

    def setup_roles(self):
        """
        Pushes the roles related metadata into the database.
        """
        log.info('Setting up roles in the database')
        discovered_roles = self._load_roles_from_files()

        for role, role_info in iteritems(discovered_roles):
            for version, version_details in role_info.items():
                try:
                    self.save_role_in_db(role, version, version_details)
                except KeyError:
                    # Skip this role and continue. We do a best effort attempt to
                    # load roles.
                    log.exception('Error saving the role %s in DB', role)

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
                    for svc, details in iteritems(data):
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
            engineHandle = create_engine(self.connectstr,
                                         **self.db_connection_options)

        return engineHandle

    @staticmethod
    def _has_uncommitted_changes(session):
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
            """
            Calculate the remaining connections and check them against
            a threshold value.
            If the number of remaining connections is less than the
            threshold, then log a warning message. Else keep logging a
            debug message with the Queuepool information.
            Note: All other pool types except QueuePool do not support
            functions like size() and checkedout(). Also there is no
            explicit way of finding out if the pool is QueuePool apart
            from looking at the status of the pool.
            """
            pool_status = self.dbengine.pool.status()
            if pool_status not in ['NullPool', 'StaticPool', 'AssertionPool']:
                pool_rem_conns = self.dbengine.pool.size() - self.dbengine.pool.checkedout()
                if pool_rem_conns <= self.pool_rem_conns_threshold :
                   log.warn('Connection pool status: %s', self.dbengine.pool.status())
                else:
                   log.debug('Connection pool status: %s', self.dbengine.pool.status())
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

    def _get_default_settings(self, role_name, version=None):
        """
        Requires that the role exists in the database.
        """
        if not version:
            role = self.query_role(role_name)
        else:
            role = self.query_role_with_version(role_name, version)
        default_settings = {}
        for default_setting_name, default_setting in iteritems(role.customizable_settings):
                default_settings[default_setting_name] = default_setting['default']
        return default_settings

    @staticmethod
    def _update_settings_with_defaults(settings, default_settings, role_name):
        """
        Update with defaults if they were not overwritten
        """
        for key, val in iteritems(default_settings):
            if key not in settings[role_name]:
                settings[role_name][key] = val

    def insert_update_host(self, host_id, host_details, role_name,
                           version, settings_to_add):
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
                        default_settings = self._get_default_settings(role_name, version)

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

    def update_host_info(self, host_id, host_info):
        """
        Update the host entry in the database with the specified info.
        :param str host_id: ID of the host
        :param dict host_info: Dictionary containing keys and values to update.
        """
        with self.dbsession() as session:
            try:
                host = session.query(Host).filter_by(id=host_id).first()

                table_columns = {attr.name for attr in host.__table__.columns}

                for column_name, new_value in iteritems(host_info):
                    if column_name in table_columns:
                        setattr(host, column_name, new_value)
                    else:
                        log.warning("Attempt to update nonexistent column '%s' "
                                    "in hosts table for host ID %s.",
                                    column_name, host_id)

                if session.is_modified(host):
                    log.info('Updated info for %s to %s', host_id, host_info)
            except:
                log.exception('Failed to update host %s with %s',
                              host_id, host_info)
                raise

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
        desiredconfig = self._validate_role_config(details['config'])
        customizable_settings = self._validate_role_config(
                                    details['customizable_settings'])

        new_role = Role(id=role_id,
                        rolename=name,
                        version=version,
                        displayname=details['display_name'],
                        description=details['description'],
                        desiredconfig=desiredconfig,
                        active=True,
                        customizable_settings=customizable_settings,
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

    def query_role_with_version(self, role_name, version):
        log.info('Querying role %s, version %s', role_name, version)
        with self.dbsession() as session:
            try:
                result = session.query(Role).filter_by(rolename=role_name, version=version).first()
            except NoResultFound:
                log.exception('No role %s, version %s found', role_name, version)
                result = None

        return result

    @staticmethod
    def _build_host_attributes(host_details, fetch_role_ids):
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
           for assoc in host_details.roles:
               roles.append(assoc.role.id)
        else:
            for assoc in host_details.roles:
                roles.append(assoc.role.rolename)

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
        out = None
        with self.dbsession() as session:
            try:
                result = session.query(Host).filter_by(id=host_id).first()
                if result:
                    out = [assoc.role for assoc in result.roles]
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
                assigned_apps_including_deauthed_roles = {}
                current_role_states = {}
                for role_assoc in host.roles:
                    desiredconfig = self._substitute_host_role_params(
                        host.id,
                        role_assoc.role.rolename,
                        role_assoc.role.desiredconfig)
                    assigned_apps_including_deauthed_roles.update(desiredconfig)

                    if role_states.role_is_authed(role_assoc.current_state):
                        assigned_apps.update(desiredconfig)

                    current_role_states[role_assoc.role_id] = \
                                        role_assoc.current_state

                out[host.id] = {
                    'hostname': host.hostname,
                    'hostosfamily': host.hostosfamily,
                    'hostarch': host.hostarch,
                    'hostosinfo': host.hostosinfo,
                    'lastresponsetime': host.lastresponsetime,
                    'responding': host.responding,
                    'apps_config': assigned_apps,
                    'apps_config_including_deauthed_roles':
                        assigned_apps_including_deauthed_roles,
                    'role_settings': host.role_settings,
                    'role_details': [assoc.role for assoc in host.roles],
                    'role_states': current_role_states
                    }

        return out

    def associate_role_to_host(self, host_id, role_name, version=None):
        """
        Associate a role to the host.
        :param str host_id: ID of the host
        :param str role_name: ID of the role
        :return: True if the role association is new, false otherwise
        """
        log.info('Adding role %s to host %s', role_name, host_id)
        with self.dbsession() as session:
            try:
                host = session.query(Host).filter_by(id=host_id).first()
                if not version:
                    role = session.query(Role).filter_by(rolename=role_name,
                                                         active=True).first()
                else:
                    role = session.query(Role).filter_by(rolename=role_name,
                                                         version=version).first()

                # in an upgrade, the active role will not match the currently
                # associated role. Just update the role.
                old_role_id = None
                for assoc in host.roles:
                    if assoc.role.rolename == role_name:
                        old_role_id = assoc.role.id
                        break
                if old_role_id:
                    session.query(HostRoleAssociation
                                 ).filter_by(host_id=host_id,
                                             role_id=old_role_id
                                 ).update({'role_id': role.id})
                    session.commit()
                    return False
                else:
                    # role not found in current associations, make a new one:
                    assoc = HostRoleAssociation(
                            current_state=str(role_states.NOT_APPLIED))
                    assoc.host = host
                    assoc.role = role
                    host.roles.append(assoc)
                    return True
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
                    log.warn('Host %s already has rabbit credentials for role %s',
                             host_id, role_name)
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
        :param str role_name: name of the role (not the id)
        """
        # the delete query doesn't dirty the session, so we can't use
        # dbsession()
        session = self.session_maker()
        role_ids = session.query(Role.id).filter_by(rolename=role_name).subquery()
        removed = session.query(HostRoleAssociation
                               ).filter_by(host_id=host_id
                               ).filter(HostRoleAssociation.role_id.in_(role_ids)
                               ).delete(synchronize_session='fetch')
        session.commit()
        session.close()
        if removed == 0:
            log.warn('No %s role association with host %s', role_name, host_id)
            return False
        elif removed > 1:
            log.error('Something is very wrong, %d  %s role associations '
                      'with host %s', removed, role_name, host_id)
            return False
        else:
            log.info('Removed %s role state from host %s', role_name, host_id)
            return True

    def advance_role_state(self, host_id, role_name, current_state, new_state):
        """
        Update the state of a host role association. The update fails if
        the assumed current_state is incorrect.
        :param host_id: ID of the host
        :param rolename: name of the role
        :param current_state: current role state
        :param new_state: updated state value
        :returns: True if we successfully update 1 row
        """
        if not role_states.legal_transition(current_state, new_state):
            raise role_states.InvalidState(current_state, new_state)

        # the update query doesn't dirty the session, so we can't use
        # dbsession()
        session = self.session_maker()
        role_ids = session.query(Role.id).filter_by(rolename=role_name).subquery()
        updated = session.query(HostRoleAssociation
                    ).filter_by(host_id=host_id
                    ).filter(HostRoleAssociation.role_id.in_(role_ids)
                    ).filter_by(current_state=str(current_state)
                    ).update({'current_state': str(new_state)},
                             synchronize_session='fetch')
        session.commit()
        session.close()
        if updated == 0:
            return False
        elif updated > 1:
            log.error('Something is very wrong, %d  %s role associations '
                      'with host %s in state %s',
                      updated, role_name, host_id, current_state)
            return False
        else:
            log.info('Advanced %s role state for host %s from %s to %s',
                     role_name, host_id, current_state, new_state)
            return True

    def get_all_role_associations(self, host_id):
        """
        Get all the role association objects along with roles for a host.
        The associations and roles are expunged (detached) from the session
        and returned.
        """
        session = self.session_maker()
        entities = session.query(HostRoleAssociation
                                ).filter_by(host_id=host_id
                                ).all()
        for entity in entities:
            session.expunge(entity.role)
            session.expunge(entity)
        session.commit()
        session.close()
        return entities

    def get_current_role_association(self, host_id, role_name):
        """
        Get the role association objects along with role given a host_id and
        rolename. The association and role are expunged (detached) from the
        session and returned.
        """
        session = self.session_maker()
        role_ids = session.query(Role.id).filter_by(rolename=role_name).subquery()
        entity = session.query(HostRoleAssociation
                              ).filter_by(host_id=host_id
                              ).filter(HostRoleAssociation.role_id.in_(role_ids)
                              ).one_or_none()
        if entity:
            session.expunge(entity)
        session.commit()
        session.close()
        return entity

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

    def move_new_state(self, host_id, role_name, start_state,
                       success_state, failure_state):
        """
        Create a context manager that moves to a new state when the body
        completes.
        :param host_id: the host id
        :param role_name: the name of the role to transition
        :param start_state: assumed current state
        :param success_state: move here on body success
        :param failure_state: move here on body failure
        """
        class _move_new_state(object):
            def __init__(self, db):
                self.db = db

            def __enter__(self):
                log.debug('Attempting to transition from %s->%s',
                          start_state, success_state)

            def __exit__(self, exc_type, exc, traceback):
                if exc:
                    # body failed, move to failure state
                    log.error('Exception %s:%s, traceback = %s', exc_type,
                              exc, traceback)
                    if start_state == failure_state:
                        log.error('%s: (%s) action failed for move from %s to '
                                  '%s, remaining in %s', host_id, role_name,
                                  start_state, success_state, start_state)
                    else:
                        log.error('%s: (%s) failed to run actions to move to '
                                  '%s, moving to %s', host_id, role_name,
                                  success_state, failure_state)

                        if not self.db.advance_role_state(host_id, role_name,
                                                          start_state,
                                                          failure_state):
                            log.error('%s (%s): failed to transition from %s '
                                      'to error state %s', host_id,
                                      role_name, start_state, failure_state)
                else:
                    # body succeeded, move to new state
                    if not self.db.advance_role_state(host_id, role_name,
                                                      start_state,
                                                      success_state):
                        log.error('%s (%s): failed to transition from %s to success '
                                  'state %s', host_id, role_name, start_state,
                                  success_state)
                    else:
                        log.info('%s (%s): successfully moved to the %s state',
                                 host_id, role_name, success_state)
        return _move_new_state(self)
