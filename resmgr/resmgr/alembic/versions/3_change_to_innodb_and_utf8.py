"""
Changes all tables to use:
    - utf8 character sets
    - utf8 collation
    - InnoDB engine

Also sets the database default charset/collation to utf8.

Revision ID: 3
Revises: 2
Create Date: 2015-2-2 16:29:50.428966

"""

# revision identifiers, used by Alembic.
revision = '3'
down_revision = '2'

from alembic import op

def upgrade():
    conn = op.get_bind()
    table_names = set(table.values()[0] for table in
                     conn.execute("show tables").fetchall())
    stmt = 'set foreign_key_checks=0;'
    stmt += ('ALTER DATABASE resmgr '
            'CHARACTER SET utf8 '
            'COLLATE utf8_unicode_ci;')
    for table_name in table_names:
        stmt += ('ALTER TABLE %s '
                 'CONVERT TO CHARACTER SET utf8 COLLATE utf8_unicode_ci;'
                 % table_name)
        stmt += ('ALTER TABLE %s '
                 'ENGINE = InnoDB;'
                 % table_name)
    stmt += 'set foreign_key_checks=1;'
    conn.execute(stmt)

def downgrade():
    pass

