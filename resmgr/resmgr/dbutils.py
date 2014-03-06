# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'Platform9'

import json

from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, backref
from sqlalchemy.orm.exc import NoResultFound

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
                                  Column('rolename', String(60),
                                         ForeignKey('roles.rolename')))

#TODO: Move this to a configuration file?
_roles = {
    'pf9-ostackhost': {
        'name': 'Openstack host',
        'description': 'Host assigned to run OpenStack Software',
        'config': {
            'version': '%(version)s',
            'running': True,
            'url': 'http://%(du_host)s/ostackhost/pf9-ostackhost-%(version)s'
                   '.x86_64.rpm',
            'config': {
                'nova': {
                    'DEFAULT': {
                        'rabbit_host': '%(du_host)s',
                        'my_ip': '%(du_host)s',
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

    rolename = Column(String(60), primary_key=True)
    name = Column(String(60))
    description = Column(String(256))
    desiredconfig = Column(String(1024))

    def __repr__(self):
        return "<Role(rolename='%s',name='%s',description='%s',desiredconfig='%s')>" % \
                (self.rolename, self.name, self.description, self.desiredconfig)


class Host(Base):
    """The ORM class for the hosts table in the database."""
    __tablename__ = 'hosts'

    id = Column(String(50), primary_key=True)
    hostname = Column(String(256))
    hostosfamily = Column(String(256))
    hostarch = Column(String(50))
    hostosinfo = Column(String(256))
    roles = relationship("Role", secondary=role_host_assoc_table,
                          backref='hosts', collection_class=set)

    def __repr__(self):
        return "<Host(id='%s', hostname='%s', hostosfamily='%s', hostarch='%s', " \
               "hostosinfo='%s')>" % (self.id, self.hostname, self.hostosfamily,
                self.hostarch, self.hostosinfo)

class ResMgrDB(object):
    """
    Provides abstraction over the ORM classes. Provides DB functionality relating
    to the resource manager.
    """
    def __init__(self, dburi):
        """
        Constructor
        :param str dburi: Connect string for the database.
        """
        self.connectstr = dburi
        self._init_db()

    def _init_db(self):
        """Initializes the database tables for Resource Manager"""
        Base.metadata.create_all(self.dbengine)
        # Populate/Update the roles table, if needed.
        self.setup_roles()

    def setup_roles(self):
        """
        Pushes the roles related metadata into the database.
        """
        for k, v in _roles.iteritems():
            config_str = json.dumps(v['config'])
            self.insert_update_role(k, v['name'], v['description'], config_str)

    @property
    def dbengine(self):
        """Get the database engine instance. If uninitialized, it will create one."""
        global engineHandle

        if not engineHandle:
            engineHandle = create_engine(self.connectstr)

        return engineHandle

    @property
    def dbsession(self):
        """Get the database session instance to run database operations."""
        sessionmkr = sessionmaker(bind=self.dbengine)
        session = sessionmkr()
        return session


    def add_new_host(self, host_id, host_details):
        """
        Add a new host into the database. The host details passed is a
        dictionary of host details. It should contain hostname, os_family,
        arch, os_info.
        :param str host_id: ID of the host to be added
        :param dict host_details: Dictionary of the host details that
         needs to be added.
        """

        session = self.dbsession
        new_host = Host(id=host_id,
                                hostname=host_details['hostname'],
                                hostosfamily=host_details['os_family'],
                                hostarch=host_details['arch'],
                                hostosinfo=host_details['os_info'])

        try:
            session.add(new_host)
        except Exception:
            session.rollback()
        else:
            session.commit()

    def delete_host(self, host_id):
        """
        Removes a host entry from the database.
        :param str host_id: Host ID to be purged from the database.
        """
        session = self.dbsession
        del_host = session.query(Host).filter_by(id=host_id).first()
        try:
            session.delete(del_host)
        except:
            session.rollback()
        else:
            session.commit()


    def insert_update_role(self, role_name, name, description, desired_config):
        """
        Insert or update a role in the database. If the role already exists in
        database, an update is performed. Otherwise, the new role is inserted
        into the database.
        :param str role_name: ID of the role
        :param str name: Name of the role
        :param str description: Description of the role
        :param dict desired_config: Actual configuration or the configuration
        template of the role.
        """
        session = self.dbsession
        new_role = Role(rolename=role_name,
                        name=name,
                        description=description,
                        desiredconfig=desired_config)

        try:
            session.merge(new_role)
        except:
            session.rollback()
        else:
            session.commit()

    def query_role(self, role_name):
        """
        Query the attributes of a particular role from the database.
        :param str role_name: ID of the role.
        :return: Role object with the role attributes. None if role is not present
        :rtype: Role
        """
        session = self.dbsession
        try:
            result = session.query(Role).filter_by(rolename=role_name).first()
        except NoResultFound:
            result = None

        return result

    def query_roles(self):
        """
        Queries all the roles present in the database.
        :return: List of Role objects
        :rtype: list
        """
        session = self.dbsession

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
        session = self.dbsession
        try:
            result = session.query(Host).filter_by(id=host_id).first()
        except NoResultFound:
            result = None

        return result

    def query_hosts(self):
        """
        Query all the hosts in the database
        :return: list of host objects
        :rtype: list
        """
        session = self.dbsession
        results = session.query(Host).all()
        return results

    def associate_role_to_host(self, host_id, role_name):
        """
        Associate a role to the host.
        :param str host_id: ID of the host
        :param str role_name: ID of the role
        """
        session = self.dbsession
        host = session.query(Host).filter_by(id=host_id).first()
        role = session.query(Role).filter_by(rolename=role_name).first()
        host.roles.add(role)

        if session.dirty:
            session.commit()

    def remove_role_from_host(self, host_id, role_name):
        """
        Remove a role from a given host
        :param str host_id: ID of the host
        :param str role_name: ID of the role
        """
        session = self.dbsession
        host = session.query(Host).filter_by(id=host_id).first()
        role = session.query(Role).filter_by(rolename=role_name).first()
        host.roles.remove(role)

        if session.dirty:
            session.commit()

    def update_roles_for_host(self, host_id, roles):
        """
        Updates the roles associated with a particular host.
        :param str host_id: ID of the host
        :param list roles: list of role IDs to associated with the host.
        """
        session = self.dbsession
        host = session.query(Host).filter_by(id=host_id).first()
        roles_set = set(roles)
        host.roles = roles_set

        if session.dirty:
            session.commit()

