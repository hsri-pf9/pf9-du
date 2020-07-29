"""
Encrypts the password in rabbit credentials table.

Revision ID: 17
Revises: 16
Create Date: 2020-08-25 17:35:16.292857

"""

# revision identifiers, used by Alembic.
revision = '17'
down_revision = '16'

from alembic import op
import sqlalchemy as sa
from resmgr.dbutils import SafeValue
from sqlalchemy import String

def upgrade():
    sv = SafeValue()
    connection = op.get_bind()
    results = connection.execute('select * from rabbit_credentials').fetchall()

    with op.batch_alter_table('rabbit_credentials') as batch_op:
        batch_op.alter_column('password', type_=SafeValue(60))

    for host_id, rolename, userid, old_plain_password in results:
        new_encrypted_password = sv.process_bind_param(old_plain_password, None)
        update_str = 'update rabbit_credentials set password="' + new_encrypted_password + \
                     '" where host_id="' + host_id + '" and rolename="' + rolename + \
                     '" and userid="' + userid + '"'
        connection.execute(update_str)

def downgrade():
    sv = SafeValue()
    connection = op.get_bind()
    results = connection.execute('select * from rabbit_credentials').fetchall()
    for host_id, rolename, userid, old_encrypted_password in results:
        new_decrypted_password = sv.process_result_value(old_encrypted_password, None)
        update_str = 'update rabbit_credentials set password="' + new_decrypted_password + \
                     '" where host_id="' + host_id + '" and rolename="' + rolename + \
                     '" and userid="' + userid + '"'
        connection.execute(update_str)
    with op.batch_alter_table('rabbit_credentials') as batch_op:
        batch_op.alter_column('password', type_=String(60))
