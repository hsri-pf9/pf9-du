# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

import os

from alembic import command
from alembic.config import Config
from six.moves.configparser import ConfigParser

RESMGR_CONF_PATH = '/etc/pf9/resmgr.conf'

def _get_resmgr_db_url():
    resmgr_conf = ConfigParser()
    resmgr_conf.read(RESMGR_CONF_PATH)
    return resmgr_conf.get('database', 'sqlconnectURI')

def migrate_db(revision="head"):

    # Update alembic.ini with resmgr's db url
    resmgr_lib_dir = os.path.dirname(__file__)
    alembic_conf_filename = os.path.join(resmgr_lib_dir, 'alembic.ini')
    alembic_conf = Config(alembic_conf_filename)
    alembic_conf.set_main_option('sqlalchemy.url', _get_resmgr_db_url())

    # Upgrade to the revision
    migration_scripts = os.path.join(resmgr_lib_dir, 'alembic')
    alembic_conf.set_main_option("script_location", migration_scripts)
    command.upgrade(alembic_conf, revision)

