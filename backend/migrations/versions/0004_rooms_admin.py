"""Online rooms and server managed administrator roles."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision='0004'
down_revision='0003'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('audit_events',sa.Column('details',JSONB,nullable=False,server_default='{}'))
    op.add_column('users',sa.Column('is_admin',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.create_table('rooms',sa.Column('id',sa.String(36),primary_key=True),sa.Column('owner_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('code',sa.String(8),unique=True,nullable=False),sa.Column('version',sa.Integer,nullable=False),sa.Column('state',JSONB,nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_rooms_owner_id','rooms',['owner_id'])
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname='out_app') THEN
    GRANT SELECT,INSERT,UPDATE,DELETE ON rooms TO out_app;
    REVOKE UPDATE ON users FROM out_app;
    GRANT UPDATE (username,email,password_hash) ON users TO out_app;
    END IF; END $$""")

def downgrade():
    op.drop_column('audit_events','details')
    op.drop_table('rooms'); op.drop_column('users','is_admin')
