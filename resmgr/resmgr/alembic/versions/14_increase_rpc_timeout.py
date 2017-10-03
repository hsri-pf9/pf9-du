"""
Increase rpc_response_timeout in OVS agent to 240
This was added to role with default of 60 in 3.0
Revision ID: 14
Revises: 13
Create Date: 2015-08-20 14:33:57.368631
"""

# revision identifiers, used by Alembic.
revision = '14'
down_revision = '13'

from alembic import op
import json
import logging
log = logging.getLogger(__name__)

def upgrade():
    conn = op.get_bind()

    # Increase rpc_response_timeout to new default of 240 in host role DB
    log.info("Starting upgrade")
    sql_query = 'select id, hostname, role_settings from hosts;'
    hosts = conn.execute(sql_query)
    hosts_list = hosts.fetchall()
    for host in hosts_list:
        host_id = host[0]
        hostname = host[1]
        role_settings = json.loads(host[2])

        if 'pf9-neutron-ovs-agent' in role_settings:
            log.info("Host {0} ({1}) has pf9-neutron-ovs-agent role".format(
                     host_id, hostname))
            log.info("Current role_settings:\n{0}".format(json.dumps(role_settings)))
            rpc_response_timeout = role_settings["pf9-neutron-ovs-agent"]["rpc_response_timeout"]

            if rpc_response_timeout and (rpc_response_timeout == "60" or rpc_response_timeout == "120"):
                # Increase value to 240, originally was 60 when added as customizeable setting in 3.0
                # so we need DB mibgration for upgraded hosts to take on new default value
                # Was increased to 120 briefly,might have manually changed it on some customers
                # Either way, enforce default minimum value of 240 sec
                role_settings["pf9-neutron-ovs-agent"]["rpc_response_timeout"] =  "240"

            # Update the SQL entry
            stmt = "update hosts set role_settings=%s where id=%s"
            log.info("New role settings:\n{0}".format(json.dumps(role_settings)))
            conn.execute(stmt, (json.dumps(role_settings), host_id))
    return

def downgrade():
    pass

