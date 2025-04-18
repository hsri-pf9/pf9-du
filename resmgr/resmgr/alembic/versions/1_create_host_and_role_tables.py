"""create host and role tables

Revision ID: 1
Revises: None
Create Date: 2014-10-25 17:35:16.292857

"""

# revision identifiers, used by Alembic.
revision = '1'
down_revision = None

from alembic import op
from sqlalchemy import (Column, String, ForeignKey, Boolean, DateTime,
                        UniqueConstraint)

def upgrade():
    op.create_table(
        'roles',
        Column('id', String(120), primary_key=True),
        Column('rolename', String(60)),
        Column('version', String(60)),
        Column('displayname', String(60)),
        Column('description', String(256)),
        Column('desiredconfig', String(2048)),
        Column('active', Boolean()),
        UniqueConstraint('rolename', 'version', name='constraint1')
    )

    op.create_table(
        'hosts',
        Column('id', String(50), primary_key=True),
        Column('hostname', String(256)),
        Column('hostosfamily', String(256)),
        Column('hostarch', String(50)),
        Column('hostosinfo', String(256)),
        Column('lastresponsetime', DateTime(), default=None),
        Column('responding', Boolean)
    )

    op.create_table(
        'host_role_map',
        Column('res_id', String(50), ForeignKey('hosts.id')),
        Column('rolename', String(120), ForeignKey('roles.id'))
    )

def downgrade():
    op.drop_table('roles')
    op.drop_table('hosts')
    op.drop_table('host_role_map')
