"""Index temporary data by age for scheduled retention cleanup."""
from alembic import op

revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_rooms_created_at', 'rooms', ['created_at'])
    op.create_index('ix_games_created_at', 'games', ['created_at'])


def downgrade():
    op.drop_index('ix_games_created_at', table_name='games')
    op.drop_index('ix_rooms_created_at', table_name='rooms')
