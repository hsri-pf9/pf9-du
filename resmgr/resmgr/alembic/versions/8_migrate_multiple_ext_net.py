"""
Handle upgrade from single external network to multiple external networks
Always add OVS bridge_mappings for external, and add label to ml2_type_flat and ml2_type_vlan
Revision ID: 8
Revises: 7
Create Date: 2015-08-20 14:33:57.368631
"""

# revision identifiers, used by Alembic.
revision = '8'
down_revision = '7'

from alembic import op
import json
import logging
log = logging.getLogger(__name__)

def upgrade():
    conn = op.get_bind()

    # Delete config from L3 Agent, migrate to OVS Agent bridge mapping
    log.info("Starting upgrade")
    sql_query = 'select id, hostname, role_settings from hosts;'
    hosts = conn.execute(sql_query)
    hosts_list = hosts.fetchall()
    for host in hosts_list:
        host_id = host[0]
        hostname = host[1]
        role_settings = json.loads(host[2])

        if 'pf9-neutron-l3-agent' in role_settings and 'pf9-neutron-ovs-agent' in role_settings:
            log.info("Host {0} ({1}) has pf9-neutron-l3-agent role and ovs-agent role".format(
                     host_id, hostname))
            log.info("Current role_settings:\n{0}".format(json.dumps(role_settings)))
            l3agent_settings = role_settings["pf9-neutron-l3-agent"]
            bridge_mappings = role_settings["pf9-neutron-ovs-agent"]["bridge_mappings"]

            if "external_network_bridge" not in l3agent_settings:
                log.info("No external_network_bridge defined. Nothing to do...")
                continue

            elif "external:" in bridge_mappings:
                log.info("Bridge mappings already has external label")

            else:
                # bridge_mapping for external not present, move the config from l3agent
                br_ext = l3agent_settings["external_network_bridge"]
                external_mapping = "external:" + br_ext
                if len(bridge_mappings) > 0:
                    new_bridge_mappings = external_mapping + "," + bridge_mappings
                else:
                    new_bridge_mappings = external_mapping
                role_settings["pf9-neutron-ovs-agent"]["bridge_mappings"] =  new_bridge_mappings


            # external_network_bridge and gateway_external_network_id MUST be empty
            role_settings["pf9-neutron-l3-agent"]["external_network_bridge"] = ""
            role_settings["pf9-neutron-l3-agent"]["gateway_external_network_id"] = ""

            # Update the SQL entry
            stmt = 'update hosts set role_settings=\'{0}\' where id="{1}"'.format(
                    json.dumps(role_settings), host_id)
            log.info("New role settings:\n{0}".format(json.dumps(role_settings)))
            conn.execute(stmt)


    # Set ML2 plugin config to support external network
    sql_query = "select service_name, settings from service_configs where service_name = 'neutron-server';"
    service = conn.execute(sql_query)
    neutron_service = service.fetchall()
    neutron_service = neutron_service[0]
    service_name = neutron_service[0]
    neutron_settings = json.loads(neutron_service[1])

    if "ml2" in neutron_settings:
        # Prior to 2.3 release, never had a ml2_type_flat section, so create it
        neutron_settings["ml2"]["ml2_type_flat"] = {}
        neutron_settings["ml2"]["ml2_type_flat"]["flat_networks"] = "*"

        log.info("Setting [ml2_type_flat] flat_networks = *")

        if "ml2_type_vlan" in neutron_settings["ml2"]:
            vlanranges = neutron_settings["ml2"]["ml2_type_vlan"]["network_vlan_ranges"]
            if (len(vlanranges) == 0) or (vlanranges == "PF9REMOVED"):
                new_vlanranges = "external"
            else:
                new_vlanranges = "external," + vlanranges

            neutron_settings["ml2"]["ml2_type_vlan"]["network_vlan_ranges"] = new_vlanranges
            log.info("Setting network_vlan_ranges = {0}".format(new_vlanranges))

        stmt = 'update service_configs set settings=\'{0}\' where service_name="{1}"'.format(
        json.dumps(neutron_settings), service_name)
        conn.execute(stmt)

    return

def downgrade():
    pass

