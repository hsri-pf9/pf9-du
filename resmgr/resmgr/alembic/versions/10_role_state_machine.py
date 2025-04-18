# Copyright (c) 2016 Platform9 Systems Inc. All Rights Reserved.

"""
Adds support for role states.
Revision ID: 10
Revises: 9
Create Date: 2016-8-4 0:0:0.0
"""

# revision identifiers, used by Alembic.
revision = '10'
down_revision = '9'

import logging

from alembic import op
from resmgr.role_states import APPLIED, NOT_APPLIED
from sqlalchemy import Column, String
from sqlalchemy.sql import text

LOG = logging.getLogger(__name__)

def upgrade():
    """
    Add current state value to host_role_map. Not that existing values
    get the value 'applied', while new ones get 'not-applied' if the
    insert doesn't include a value. It must be populated.
    """
    LOG.info('adding current state column to host_role_map')
    op.add_column('host_role_map',
                  Column('current_state', String(120),
                         nullable=False, server_default=str(NOT_APPLIED))
    )
    op.get_bind().execute(text("UPDATE host_role_map set current_state=:state"),
                          state=str(APPLIED))

def downgrade():
    LOG.info('dropping current state column from host_role_map')
    op.drop_column('host_role_map', 'current_state')

