"""
Adds a service configuration related table.
Revision ID: 6
Revises: 5
Create Date: 2015-10-20 14:33:57.368631
"""

# revision identifiers, used by Alembic.
revision = '6'
down_revision = '5'

from alembic import op
from sqlalchemy import Column, Text, String
import logging

log = logging.getLogger(__name__)

service_config_tablename = 'service_configs'


def upgrade():
    log.info("Creating table %s", service_config_tablename)
    op.create_table(
        service_config_tablename,
        Column('service_name', String(128), primary_key=True),
        Column('config_script_path', String(512)),
        Column('settings', Text()),
        mysql_engine='InnoDB'
    )


def downgrade():
    op.drop_table(service_config_tablename)
