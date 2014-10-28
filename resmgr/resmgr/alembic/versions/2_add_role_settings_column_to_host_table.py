"""Add role settings column to host table

Revision ID: 2
Revises: 1
Create Date: 2014-10-26 16:29:50.428966

"""

# revision identifiers, used by Alembic.
revision = '2'
down_revision = '1'

from alembic import op
from sqlalchemy import Column, String


def upgrade():
    op.add_column(
        'hosts',
        Column('role_settings', String(2048), default="{}")
    )
    op.add_column(
        'roles',
        Column('customizable_settings', String(2048), default="{}")
    )

def downgrade():
    op.drop_column('hosts', 'role_settings')

