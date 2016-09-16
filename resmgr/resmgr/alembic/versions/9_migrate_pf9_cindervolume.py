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


conn = op.get_bind()

def get_role_id(rolename):
    stmt = 'select id from roles where rolename="%s" and active="1"' % rolename
    res  = conn.execute(stmt).fetchone()
    if res != None:
      return res['id']
    else:
      return None

def insert_dummy_role(rolename):
    log.info("Adding a dummy %s role" % rolename)
    version = "2.2.0-000"
    stmt = 'insert into roles values (%s, %s, %s,"Block Storage", "Temp role", "{}", 1, "{}", "{}")'
    res  = conn.execute(stmt, rolename + '-temp', rolename, version)

def upgrade():
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
          driver_role = driver_role_mapping[current_driver]
          if current_driver in driver_role_mapping:
              role_settings[driver_role] = current_settings
          else:
              role_settings['pf9-cindervolume-other'] = current_settings
          stmt = 'update hosts set role_settings=%s where id=%s'
          log.info("New role settings:\n{0}".format(json.dumps(role_settings)))
          conn.execute(stmt, json.dumps(role_settings), host_id)

          # Delete pf9-cindervolume
          role_id = get_role_id("pf9-cindervolume")
          log.info(role_id)
          if role_id != None:
              # Add a dummy pf9-cindervolume-* first
              insert_dummy_role("pf9-cindervolume-base")
              insert_dummy_role(driver_role)

              log.info("Deleting pf9-cindervolume host_role_map association")
              stmt = 'delete from host_role_map where rolename="{0}"'.format(role_id)
              conn.execute(stmt)

              log.info("Deleting pf9-cindervolume role")
              stmt = 'delete from roles where rolename="pf9-cindervolume"'
              conn.execute(stmt)

          # Associate host and roles
          # cindervolume-base
          stmt = 'insert into host_role_map values (%s, %s)'
          cindervolume_base_id = get_role_id("pf9-cindervolume-base")
          conn.execute(stmt, host_id, cindervolume_base_id)

          # + custom cindervolume driver role
          stmt = 'insert into host_role_map values (%s, %s)'
          role_id = get_role_id(driver_role)
          conn.execute(stmt, host_id, role_id)

      elif 'pf9-cindervolume-base' in role_settings:
          log.info("Host {0} ({1}) is already up-to-date".format(host_id, hostname))
def downgrade():
    pass
