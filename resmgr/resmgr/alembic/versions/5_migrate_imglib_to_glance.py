"""
Migrate imglib role settings to glance-role
Revision ID: 5
Revises: 4
Create Date: 2015-08-20 14:33:57.368631
"""

# revision identifiers, used by Alembic.
revision = '5'
down_revision = '4'

from alembic import op
import json
import logging
log = logging.getLogger(__name__)

def populate_glance_role(data_dir):
    # Let users configure the endpoint address in the UI
    return { "region": "RegionOne",
             "filesystem_store_datadir": data_dir,
             "endpoint_address": ""
           }

def upgrade():
    conn = op.get_bind()
    log.info("Starting upgrade")
    stmt = 'select id, hostname, role_settings from hosts;'
    hosts = conn.execute(stmt)
    hosts_list = hosts.fetchall()
    for host in hosts_list:
        host_id = host[0]
        hostname = host[1]
        role_settings = json.loads(host[2])

        if 'pf9-imagelibrary' in role_settings and 'pf9-glance-role' not in role_settings:
            log.info("Host {0} ({1}) has pf9-imagelibrary and no pf9-glance-role".format(
                     host_id, hostname))
            log.info("Current role_settings:\n{0}".format(json.dumps(role_settings)))
            imglib_settings = role_settings["pf9-imagelibrary"]

            if 'data_directory' in imglib_settings:
                data_dir = imglib_settings["data_directory"]
                role_settings["pf9-glance-role"] =  populate_glance_role(data_dir)
                stmt = 'update hosts set role_settings=\'{0}\' where id="{1}"'.format(
                       json.dumps(role_settings), host_id)
                log.info("New role settings:\n{0}".format(json.dumps(role_settings)))
                conn.execute(stmt)
            else:
                log.info("No data_directory in pf9-imagelibrary. Skipping...")

        elif 'pf9-imagelibrary' in role_settings and 'pf9-glance-role' in role_settings:
            log.info("Host {0} ({1}) is already up-to-date".format(host_id, hostname))
def downgrade():
    pass

