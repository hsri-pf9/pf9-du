"""
Migrate kube role download url
Revision ID: 14
Revises: 13
Create Date: 2019-03-01 12:21:00.567532
"""

# revision identifiers, used by Alembic.
revision = '14'
down_revision = '13'

from alembic import op
import json
import copy
import logging
log = logging.getLogger(__name__)

def downgrade():
    pass


def upgrade():
    # Get the id and desiredconfig for the pf9-kube role which has some token string for the url field
    # Load the desiredconfig as json, using the version field in the json, reconstruct the url field in the json
    # update the role for that specific role id with the updated json blob
    get_stmt = 'select id, desiredconfig from roles where rolename="pf9-kube" and desiredconfig like "%%pf9-kube.package_rpm%%" '
    affected_roles = conn.execute(get_stmt).fetchall()
    log.info("Retrieved %d records affected with pf9-kube versions", len(affected_roles))
    for r in affected_roles:
        desired_conf = json.loads(r[1])
        pf9kube_conf = desired_conf["pf9-kube"]
        ver = pf9kube_conf["version"]
        new_url = "http://localhost:9080/private/pf9-kube-%s.x86_64.rpm" % ver
        pf9kube_conf["url"] = new_url
        log.info("Adjusting role %s url to %s", r[0], new_url)
        update_stmt = 'update roles set desiredconfig=%s where id=%s'
        conn.execute(update_stmt, json.dumps(desired_conf), r[0])


conn = op.get_bind()

