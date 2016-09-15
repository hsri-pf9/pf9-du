"""
Migrate pf9-cindervolume role
Revision ID: 9
Revises: 8
Create Date: 2016-08-17 19:00:00.567532
"""

# revision identifiers, used by Alembic.
revision = '9'
down_revision = '8'

from alembic import op
import json
import logging
log = logging.getLogger(__name__)

def upgrade():
    conn = op.get_bind()
    log.info("Starting upgrade of pf9-cindervolume role")
    stmt = 'select id, hostname, role_settings from hosts'
    hosts = conn.execute(stmt)
    host_list = hosts.fetchall()
    for host in host_list:
      host_id  = host[0]
      hostname = host[1]
      role_settings = json.loads(host[2])

      driver_role_mapping = {
          "cinder.volume.drivers.lvm.LVMISCSIDriver": "pf9-cindervolume-lvm",
          "cinder.volume.drivers.netapp.common.NetAppDriver": "pf9-cindervolume-netapp",
          "cinder.volume.drivers.qnap.QnapISCSIDriver":  "pf9-cindervolume-qnap",
          "cinder.volume.drivers.solidfire.SolidFireDriver": "pf9-cindervolume-solidfire"
      }

      if 'pf9-cindervolume' in role_settings and 'pf9-cindervolume-base' not in role_settings:
          log.info("Host {0} ({1}) has pf9-cindervolume role and no pf9-cindervolume-base role".format(
                   host_id, hostname))
          log.info("Current role_settings:\n{0}".format(json.dumps(role_settings)))
          current_settings = role_settings.pop("pf9-cindervolume")
          current_driver = current_settings["volume_driver"]

          # auth with the pf9-cindervolume-base role by default
          role_settings["pf9-cindervolume-base"] = {}
          if current_driver in driver_role_mapping:
              role_settings[driver_role_mapping[current_driver]] = current_settings
          else:
              role_settings['pf9-cindervolume-other'] = current_settings
          stmt = 'update hosts set role_settings=%s where id=%s'
          log.info("New role settings:\n{0}".format(json.dumps(role_settings)))
          conn.execute(stmt, json.dumps(role_settings), host_id)

          # deactivate pf9-cindervolume
          log.info("Deactivating pf9-cindervolume role")
          stmt = 'update roles set active=0 where rolename="pf9-cindervolume"'
          conn.execute(stmt)
      elif 'pf9-cindervolume-base' in role_settings:
          log.info("Host {0} ({1}) is already up-to-date".format(host_id, hostname))
def downgrade():
    pass
