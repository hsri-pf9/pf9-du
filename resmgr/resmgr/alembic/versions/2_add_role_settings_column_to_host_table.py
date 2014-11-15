"""Add role settings column to host table

Revision ID: 2
Revises: 1
Create Date: 2014-10-26 16:29:50.428966

"""

# revision identifiers, used by Alembic.
revision = '2'
down_revision = '1'

import json
from alembic import op
from sqlalchemy import Column, String

default_role_settings = json.dumps({
    "pf9-ostackhost": {
        "instances_path": "/opt/pf9/data/instances"
    },
    "pf9-imagelibrary": {
        "data_directory": "/var/opt/pf9/imagelibrary/data"
    }
})

def upgrade():
    op.add_column(
        'hosts',
        Column('role_settings', String(2048),
               server_default=default_role_settings)
    )
    op.add_column(
        'roles',
        Column('customizable_settings', String(2048))
    )

def downgrade():
    op.drop_column('hosts', 'role_settings')
    op.drop_column('roles', 'customizable_settings')

