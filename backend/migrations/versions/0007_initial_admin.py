"""Grant the registered operator account its initial administrator role."""
import json
import uuid

from alembic import op
import sqlalchemy as sa

revision='0007'
down_revision='0006'
branch_labels=None
depends_on=None

ADMIN_EMAIL='pardeshianurag22@gmail.com'


def upgrade():
    connection=op.get_bind()
    user=connection.execute(
        sa.text("SELECT id, is_admin FROM users WHERE email=:email AND is_guest=false FOR UPDATE"),
        {'email':ADMIN_EMAIL},
    ).mappings().first()
    # Fresh development and test databases do not contain the production operator.
    if not user or user['is_admin']:
        return
    connection.execute(sa.text('UPDATE users SET is_admin=true WHERE id=:id'),{'id':user['id']})
    connection.execute(
        sa.text("""INSERT INTO audit_events (id, actor, details, action, resource, created_at)
                   VALUES (:audit_id, NULL, CAST(:details AS jsonb), 'admin.granted', :user_id, now())"""),
        {
            'audit_id':str(uuid.uuid4()),
            'details':json.dumps({'source':'migration_0007'}),
            'user_id':user['id'],
        },
    )


def downgrade():
    # A schema rollback must not silently remove operator access.
    pass
