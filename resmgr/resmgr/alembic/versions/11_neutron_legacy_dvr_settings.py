"""
Handle upgrade from single external network to multiple external networks
Always add OVS bridge_mappings for external, and add label to ml2_type_flat and ml2_type_vlan
Revision ID: 9
Revises: 8
Create Date: 2015-08-20 14:33:57.368631
"""

# revision identifiers, used by Alembic.
revision = '11'
down_revision = '10'

from alembic import op
import json
import logging
log = logging.getLogger(__name__)

def upgrade():
    conn = op.get_bind()
    log.info("Starting upgrade")

    # First determine if router_distributed==True in neutron-server DEFAULT section
    sql_query = "select service_name, settings from service_configs where service_name = 'neutron-server';"
    service = conn.execute(sql_query)
    neutron_service = service.fetchall()
    if len(neutron_service) == 0:
        return
    neutron_service = neutron_service[0]
    neutron_settings = json.loads(neutron_service[1])

    if "neutron" in neutron_settings and "DEFAULT" in neutron_settings["neutron"]:
        if "router_distributed" in neutron_settings["neutron"]["DEFAULT"]:
            dvr = neutron_settings["neutron"]["DEFAULT"]["router_distributed"]
        else:
            # router_distributed not set for some reason, default behavior is False
            dvr = False
    else:
        # Neutron and DEFAULT section should be present if neutron-server service installed...
        # Just assume reference arch for agents
        dvr = False

    log.info("dvr is {0}".format(dvr))

    sql_query = 'select id, hostname, role_settings from hosts;'
    hosts = conn.execute(sql_query)
    hosts_list = hosts.fetchall()
    for host in hosts_list:
        host_id = host[0]
        hostname = host[1]
        role_settings = json.loads(host[2])

        if 'pf9-neutron-l3-agent' in role_settings:
            log.info("Host {0} ({1}) has pf9-neutron-l3-agent role".format(
                     host_id, hostname))
            log.info("Current role_settings:\n{0}".format(json.dumps(role_settings)))

            if dvr == False:
                role_settings["pf9-neutron-l3-agent"]["agent_mode"] = "legacy"

        if 'pf9-neutron-ovs-agent' in role_settings:
            log.info("Host {0} ({1}) has pf9-neutron-ovs-agent role".format(
                     host_id, hostname))
            log.info("Current role_settings:\n{0}".format(json.dumps(role_settings)))

            if dvr == False:
                role_settings["pf9-neutron-ovs-agent"]["enable_distributed_routing"] = "False"
            elif dvr == True:
                # This is now a customizeable setting, with new default value. Must explicitly set it
                role_settings["pf9-neutron-ovs-agent"]["enable_distributed_routing"] = "True"

        # Update the SQL entry
        stmt = 'update hosts set role_settings=%s where id=%s'
        log.info("New role settings:\n{0}".format(json.dumps(role_settings)))
        conn.execute(stmt, (json.dumps(role_settings), host_id))

    return

def downgrade():
    pass

