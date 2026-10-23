"""Accounts, opaque sessions, owned games, audit trail and shared rate limits."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision='0001'
down_revision=None
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('users',sa.Column('id',sa.String(36),primary_key=True),sa.Column('username',sa.String(24),nullable=False,unique=True),sa.Column('email',sa.String(254),nullable=False,unique=True),sa.Column('password_hash',sa.String(256),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_table('sessions',sa.Column('token_hash',sa.String(64),primary_key=True),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('csrf',sa.String(64),nullable=False),sa.Column('expires',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_sessions_user_id','sessions',['user_id']); op.create_index('ix_sessions_expires','sessions',['expires'])
    op.create_table('games',sa.Column('id',sa.String(36),primary_key=True),sa.Column('owner_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('code',sa.String(8),nullable=False,unique=True),sa.Column('version',sa.Integer,nullable=False),sa.Column('state',JSONB,nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.CheckConstraint('version >= 0'))
    op.create_index('ix_games_owner_id','games',['owner_id'])
    op.create_table('audit_events',sa.Column('id',sa.String(36),primary_key=True),sa.Column('actor',sa.String(36)),sa.Column('action',sa.String(64),nullable=False),sa.Column('resource',sa.String(36)),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_audit_events_created_at','audit_events',['created_at'])
    op.create_table('rate_buckets',sa.Column('key',sa.String(64),primary_key=True),sa.Column('count',sa.Integer,nullable=False),sa.Column('expires',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_rate_buckets_expires','rate_buckets',['expires'])
    op.execute("CREATE FUNCTION protect_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Audit events are append only'; END; $$")
    op.execute('CREATE TRIGGER immutable_audit BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION protect_audit()')
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname='out_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON users, sessions, games, rate_buckets TO out_app;
        GRANT SELECT, INSERT ON audit_events TO out_app;
    END IF; END $$""")
def downgrade():
    for table in ['rate_buckets','audit_events','games','sessions','users']: op.drop_table(table)
    op.execute('DROP FUNCTION protect_audit()')
