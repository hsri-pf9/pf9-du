# Copyright (c) 2017 Platform9 Systems Inc. All Rights Reserved.

"""
Removes the qbert service configuration
Revision ID: 12
Revises: 11
Create Date: 2017-3-15 0:0:0.0
"""

# revision identifiers, used by Alembic.
revision = '12'
down_revision = '11'

import logging

from alembic import op
from sqlalchemy.sql import text

LOG = logging.getLogger(__name__)

def upgrade():
    """
    Drop the row for qbert from the resmgr service configuration table
    """
    LOG.info('Dropping qbert settings from the service configuration table')
    op.get_bind().execute(text("delete from service_configs where service_name=:svc"),
                          svc='qbert')

def downgrade():
    pass
