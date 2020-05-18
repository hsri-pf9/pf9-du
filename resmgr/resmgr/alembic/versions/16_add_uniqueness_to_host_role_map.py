"""create host and role tables

Revision ID: 16
Revises: 15
Create Date: 2020-05-18 17:35:16.292857

"""

# revision identifiers, used by Alembic.
revision = '16'
down_revision = '15'

from alembic import op

def upgrade():
    with op.batch_alter_table('host_role_map') as batch_op:
        batch_op.create_unique_constraint('host_role_map_unique1',
                                          ['res_id', 'rolename'])

def downgrade():
    pass
