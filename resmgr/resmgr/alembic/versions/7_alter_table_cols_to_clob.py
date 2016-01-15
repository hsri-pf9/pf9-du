"""
Alters the resmgr table large columns to CLOB
Revision ID: 7
Revises: 6
Create Date: 2016-01-14 17:46:18.030000
"""

# revision identifiers, used by Alembic
revision = '7'
down_revision = '6'


from alembic import op
from sqlalchemy import Text
import logging


log = logging.getLogger(__name__)


table_cols_map = {
        'roles': ['desiredconfig', 'customizable_settings', 'rabbit_permissions'],
        'hosts': ['role_settings']
        }


def upgrade():
    for table, cols in table_cols_map.iteritems():
        with op.batch_alter_table(table) as tab_batch:
            for c in cols:
                tab_batch.alter_column(c, type_=Text)
                log.info("Altering column %s to CLOB in table %s", c, table)


def downgrade():
    for table, cols in table_cols_map.iteritems():
        with op.batch_alter_table(table) as tab_batch:
            for c in cols:
                tab_batch.alter_column(c, type_=String(2048))
                log.info("Altering column %s to string(2048) in table %s", c, table)
