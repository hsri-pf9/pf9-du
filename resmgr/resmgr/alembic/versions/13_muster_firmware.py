# Copyright (c) 2017 Platform9 Systems Inc. All Rights Reserved.

"""
Fix convergence error due to pf9-muster transition to firmware
Revision ID: 13
Revises: 12
Create Date: 2017-4-04 0:0:0.0
"""

# revision identifiers, used by Alembic.
revision = '13'
down_revision = '12'

import logging

from alembic import op
from sqlalchemy.sql import text

LOG = logging.getLogger(__name__)

def upgrade():
    """
    Switching pf9-muster from an ordinary role requires removing some of the existing configuration
    from resmgr, or upgrades will fail, because the configuration dictionary of firmware is managed by
    bbmaster instead of resmgr. It thus does not have access to rabbit credentials, etc.
    """
    LOG.info('Deleting pf9-muster role maps')
    op.get_bind().execute(text("delete from host_role_map where rolename like 'pf9-muster_%'"))

    LOG.info('Deleting pf9-muster role info')
    op.get_bind().execute(text("delete from roles where rolename='pf9-muster'"))

    LOG.info('Deleting pf9-muster rabbit credentials')
    op.get_bind().execute(text("delete from rabbit_credentials where rolename='pf9-muster'"))

def downgrade():
    pass
