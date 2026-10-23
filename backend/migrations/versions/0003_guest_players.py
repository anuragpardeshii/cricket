"""Separate guest principals from registered accounts."""
from alembic import op
import sqlalchemy as sa
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('is_guest', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index('ix_users_is_guest', 'users', ['is_guest'])

def downgrade():
    # Do not silently turn guests into registered users.
    if op.get_bind().scalar(sa.text('SELECT EXISTS (SELECT 1 FROM users WHERE is_guest)')):
        raise RuntimeError('Remove expired guest data before downgrading guest support')
    op.drop_index('ix_users_is_guest', table_name='users')
    op.drop_column('users', 'is_guest')
