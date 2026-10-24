"""Room WebSocket tickets, voice access, and committed change notifications."""
from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('room_socket_tickets',
        sa.Column('token_hash', sa.String(64), primary_key=True),
        sa.Column('room_id', sa.String(36), sa.ForeignKey('rooms.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_hash', sa.String(64), sa.ForeignKey('sessions.token_hash', ondelete='CASCADE'), nullable=False),
        sa.Column('expires', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_room_socket_tickets_room_id', 'room_socket_tickets', ['room_id'])
    op.create_index('ix_room_socket_tickets_expires', 'room_socket_tickets', ['expires'])
    op.create_table('voice_grants',
        sa.Column('member_id', sa.String(36), primary_key=True),
        sa.Column('identity', sa.String(36), unique=True, nullable=False),
        sa.Column('room_id', sa.String(36), sa.ForeignKey('rooms.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_hash', sa.String(64), nullable=False))
    op.create_index('ix_voice_grants_room_id', 'voice_grants', ['room_id'])
    # PostgreSQL delivers NOTIFY only after commit, including writes from other workers.
    op.execute("""CREATE FUNCTION out_room_changed() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            PERFORM pg_notify('out_room_changes', COALESCE(NEW.id, OLD.id));
            RETURN NULL;
        END $$""")
    op.execute('CREATE TRIGGER out_room_changed AFTER INSERT OR UPDATE OR DELETE ON rooms FOR EACH ROW EXECUTE FUNCTION out_room_changed()')
    op.execute("""CREATE FUNCTION out_access_changed() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN PERFORM pg_notify('out_room_changes', '*'); RETURN NULL; END $$""")
    op.execute('CREATE TRIGGER out_session_changed AFTER UPDATE OR DELETE ON sessions FOR EACH STATEMENT EXECUTE FUNCTION out_access_changed()')
    op.execute('CREATE TRIGGER out_user_changed AFTER UPDATE ON users FOR EACH STATEMENT EXECUTE FUNCTION out_access_changed()')
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname='out_app') THEN
        GRANT SELECT,INSERT,UPDATE,DELETE ON room_socket_tickets,voice_grants TO out_app;
    END IF; END $$""")


def downgrade():
    op.execute('DROP TRIGGER out_user_changed ON users')
    op.execute('DROP TRIGGER out_session_changed ON sessions')
    op.execute('DROP FUNCTION out_access_changed()')
    op.execute('DROP TRIGGER out_room_changed ON rooms')
    op.execute('DROP FUNCTION out_room_changed()')
    op.drop_table('voice_grants')
    op.drop_table('room_socket_tickets')
