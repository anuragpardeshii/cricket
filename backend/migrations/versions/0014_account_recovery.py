"""One-use account recovery codes, stored only as hashes."""
from alembic import op
import sqlalchemy as sa
revision='0014'
down_revision='0013'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('account_recovery',sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),primary_key=True),sa.Column('token_hash',sa.String(64),nullable=False))
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname='out_app') THEN
        GRANT SELECT,INSERT,UPDATE,DELETE ON account_recovery TO out_app;
    END IF; END $$""")

def downgrade(): op.drop_table('account_recovery')
