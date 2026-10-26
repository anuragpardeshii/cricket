"""Durable friend groups, cups, match history and earned achievements."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('friend_groups', sa.Column('id', sa.String(36), primary_key=True), sa.Column('owner_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False), sa.Column('name', sa.String(40), nullable=False), sa.Column('invite', sa.String(64), nullable=False, unique=True), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_friend_groups_owner_id', 'friend_groups', ['owner_id'])
    op.create_table('group_members', sa.Column('group_id', sa.String(36), sa.ForeignKey('friend_groups.id', ondelete='CASCADE'), primary_key=True), sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), primary_key=True))
    op.create_table('cups', sa.Column('id', sa.String(36), primary_key=True), sa.Column('group_id', sa.String(36), sa.ForeignKey('friend_groups.id', ondelete='CASCADE'), nullable=False), sa.Column('state', JSONB, nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_cups_group_id', 'cups', ['group_id'])
    op.create_table('match_archive', sa.Column('id', sa.String(80), primary_key=True), sa.Column('group_id', sa.String(36), sa.ForeignKey('friend_groups.id')), sa.Column('data', JSONB, nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_match_archive_group_id', 'match_archive', ['group_id'])
    op.create_index('ix_match_archive_created_at', 'match_archive', ['created_at'])
    op.create_table('match_players', sa.Column('match_id', sa.String(80), sa.ForeignKey('match_archive.id', ondelete='CASCADE'), primary_key=True), sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True), sa.Column('won', sa.Boolean, nullable=False))
    op.create_table('achievements', sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True), sa.Column('code', sa.String(40), primary_key=True), sa.Column('earned_at', sa.DateTime(timezone=True), nullable=False), sa.Column('source', sa.String(80), nullable=False), sa.Column('share_token', sa.String(64), unique=True))
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname='out_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON friend_groups, group_members, cups, match_archive, match_players, achievements TO out_app;
        GRANT UPDATE (is_guest, mobile) ON users TO out_app;
    END IF; END $$""")

def downgrade():
    for table in ['achievements', 'match_players', 'match_archive', 'cups', 'group_members', 'friend_groups']:
        op.drop_table(table)
