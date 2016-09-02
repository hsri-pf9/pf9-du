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

def random_string_generator(len=16):
    return "".join([random.choice(string.ascii_letters + string.digits) for _ in
            xrange(len)])

def populate_rabbit_credentials_table(conn):
    host_roles = conn.execute('select * from host_role_map').fetchall()
    for host_id, role_id in host_roles:
        if role_id.startswith('pf9-ostackhost-vmw'):
            role_name = 'pf9-ostackhost-vmw'
        elif role_id.startswith('pf9-ostackhost'):
            role_name = 'pf9-ostackhost'
        elif role_id.startswith('pf9-imagelibrary'):
            role_name = 'pf9-imagelibrary'
        rabbit_userid = random_string_generator()
        rabbit_password = random_string_generator()
        conn.execute('insert into rabbit_credentials values ("{0}", "{1}", "{2}", "{3}")'
                     .format(host_id, role_name, rabbit_userid, rabbit_password))

def upgrade():
    op.add_column(
        'roles',
        Column('rabbit_permissions', String(2048))
    )
    conn = op.get_bind()

    if conn.engine.dialect.name != 'sqlite':
        stmt = 'alter table roles add index (rolename);'
        conn.execute(stmt)

    op.create_table(
            'rabbit_credentials',
            Column('host_id', String(50),
                   ForeignKey('hosts.id', ondelete='CASCADE'),
                   primary_key=True),
            Column('rolename', String(60),
                   ForeignKey('roles.rolename', ondelete='CASCADE'),
                   primary_key=True),
            Column('userid', String(60)),
            Column('password', String(50)),
            mysql_engine='InnoDB'
    )
    populate_rabbit_credentials_table(conn)

def downgrade():
    op.drop_table('rabbit_credentials')
    op.drop_column('roles', 'rabbit_permissions')

