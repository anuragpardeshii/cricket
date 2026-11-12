"""Apply sourced edition-specific ratings without changing saved drafts."""
import json
from pathlib import Path
from alembic import op
import sqlalchemy as sa
revision='0015'
down_revision='0014'
branch_labels=None
depends_on=None

def entries():
    return json.loads((Path(__file__).resolve().parents[1]/'data/rating_review_0015.json').read_text())

def upgrade():
    connection=op.get_bind()
    connection.execute(sa.text('SELECT pg_advisory_xact_lock(734829106)'))
    for id,p in entries().items():
        connection.execute(sa.text('UPDATE players SET rating=:new WHERE id=:id AND rating=:old'),dict(id=id,new=p['rating'],old=p['oldRating']))

def downgrade():
    connection=op.get_bind()
    for id,p in entries().items():
        connection.execute(sa.text('UPDATE players SET rating=:old WHERE id=:id AND rating=:new'),dict(id=id,new=p['rating'],old=p['oldRating']))
