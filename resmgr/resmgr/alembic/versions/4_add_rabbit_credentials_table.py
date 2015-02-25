"""
Add and populate the rabbit_credentials table.
Also, add the rabbit_permissions column to the roles table.

Revision ID: 4
Revises: 3
Create Date: 2015-2-2 16:29:50.428966

"""

# revision identifiers, used by Alembic.
revision = '4'
down_revision = '3'

import glob
import json
import logging as log
import random
import string

from alembic import op
from ConfigParser import ConfigParser
from rabbit import RabbitMgmtClient
from sqlalchemy import Column, ForeignKey, String, UniqueConstraint

RESMGR_CONF_PATH = '/etc/pf9/resmgr.conf'

def get_rabbit_permissions(config):
    """
    Return a dict that maps role names to rabbit_permissions.
    If there are multiple versions of the same role, the latest
    version will be used (since the result of the glob pattern
    will be in order).
    """
    rabbit_permissions_map = {}
    file_pattern = '%s/*/*/*.json' % config.get('resmgr',
                                                'role_metadata_location')
    for file in glob.glob(file_pattern):
        with open(file) as fp:
            try:
                # Each file should represent data for one version of a role
                data = json.load(fp)
                if not isinstance(data, dict):
                    raise RuntimeError('Invalid role metadata file %s, data is not '
                                       'of expected dict format.' % file)
                rabbit_permissions_map[data['role_name']] = data['rabbit_permissions']
            except:
                log.exception('Error loading the role metadata file %s', file)
                raise
    return rabbit_permissions_map

def random_string_generator(len=16):
    return "".join([random.choice(string.ascii_letters + string.digits) for _ in
            xrange(len)])

def populate_rabbit_credentials_table(conn):
    conf = ConfigParser()
    conf.read(RESMGR_CONF_PATH)

    rabbit_permissions_map = get_rabbit_permissions(conf)

    username = conf.get('amqp', 'username') \
            if conf.has_option('amqp', 'username') else 'resmgr'
    password = conf.get('amqp', 'password') \
            if conf.has_option('amqp', 'password') else 'resmgr'
    rabbit_mgr = RabbitMgmtClient(username, password)

    host_roles = conn.execute('select * from host_role_map').fetchall()
    for host_id, role_id in host_roles:
        if role_id.startswith('pf9-ostackhost-vmw'):
            role_name = 'pf9-ostackhost-vmw'
        elif role_id.startswith('pf9-ostackhost'):
            role_name = 'pf9-ostackhost'
        elif role_id.startswith('pf9-imagelibrary'):
            role_name = 'pf9-imagelibrary'
        rabbit_permissions = rabbit_permissions_map[role_name]
        rabbit_userid = random_string_generator()
        rabbit_password = random_string_generator()
        rabbit_mgr.create_user(rabbit_userid, rabbit_password)
        rabbit_mgr.set_permissions(rabbit_userid,
                                   rabbit_permissions['config'],
                                   rabbit_permissions['write'],
                                   rabbit_permissions['read'])
        conn.execute('insert into rabbit_credentials values ("{0}", "{1}", "{2}", "{3}")'
                     .format(host_id, role_name, rabbit_userid, rabbit_password))

def upgrade():
    op.add_column(
        'roles',
        Column('rabbit_permissions', String(2048))
    )
    conn = op.get_bind()
    stmt = 'alter table roles add index (rolename);'
    conn.execute(stmt)
    op.create_table(
            'rabbit_credentials',
            Column('host_id', String(50), ForeignKey('hosts.id'), primary_key=True),
            Column('rolename', String(60), ForeignKey('roles.rolename'), primary_key=True),
            Column('userid', String(60)),
            Column('password', String(50)),
            mysql_engine='InnoDB'
    )
    stmt = ('alter table rabbit_credentials '
            'add constraint `fk_host_id` foreign key(`host_id`) '
            'references `hosts`(`id`) on delete cascade;')
    stmt += ('alter table rabbit_credentials '
             'add constraint `fk_rolename` foreign key(`rolename`) '
             'references `roles`(`rolename`) on delete cascade;')
    conn.execute(stmt)
    populate_rabbit_credentials_table(conn)

def downgrade():
    op.drop_table('rabbit_credentials')
    op.drop_column('roles', 'rabbit_permissions')

