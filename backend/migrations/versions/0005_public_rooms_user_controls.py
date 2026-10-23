"""Room discovery, account blocking and unique normalized mobile numbers."""
from alembic import op
import sqlalchemy as sa
revision='0005'
down_revision='0004'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('users',sa.Column('is_blocked',sa.Boolean(),nullable=False,server_default=sa.false()))
    # Previous versions did not retain phone input; legacy accounts remain NULL.
    op.add_column('users',sa.Column('mobile',sa.String(16),nullable=True))
    op.create_unique_constraint('uq_users_mobile','users',['mobile'])
    op.create_check_constraint('ck_users_mobile','users',"mobile IS NULL OR mobile ~ '^\\+[1-9][0-9]{10,13}$'")
    op.create_index('uq_users_email_normalized','users',[sa.text('lower(email)')],unique=True)
    op.add_column('rooms',sa.Column('visibility',sa.String(7),nullable=False,server_default='private'))
    op.create_check_constraint('ck_rooms_visibility','rooms',"visibility IN ('public','private')")
    op.create_index('ix_rooms_visibility_created','rooms',['visibility','created_at'])
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname='out_app') THEN
        GRANT UPDATE (is_blocked) ON users TO out_app;
    END IF; END $$""")

def downgrade():
    op.drop_index('ix_rooms_visibility_created',table_name='rooms')
    op.drop_constraint('ck_rooms_visibility','rooms',type_='check'); op.drop_column('rooms','visibility')
    op.drop_index('uq_users_email_normalized',table_name='users')
    op.drop_constraint('ck_users_mobile','users',type_='check'); op.drop_constraint('uq_users_mobile','users',type_='unique')
    op.drop_column('users','mobile'); op.drop_column('users','is_blocked')
