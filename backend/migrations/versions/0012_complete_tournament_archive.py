"""Add the complete IPL and World Cup archive, preserving existing cards."""
import json
from pathlib import Path

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None

squads = sa.table('squads', sa.column('id', sa.String), sa.column('country', sa.String),
                  sa.column('tournament', sa.String), sa.column('sort_order', sa.Integer))
players = sa.table('players', sa.column('id', sa.String), sa.column('squad_id', sa.String),
                   sa.column('name', sa.String), sa.column('role', sa.String),
                   sa.column('rating', sa.Integer), sa.column('sort_order', sa.Integer))


def data():
    return json.loads((Path(__file__).resolve().parents[1] / 'data/catalog_v5.json').read_text())['squads']


def upgrade():
    connection = op.get_bind()
    connection.execute(sa.text('SELECT pg_advisory_xact_lock(734829106)'))
    for squad in data():
        squad_id = squad['players'][0]['id'].split('-')[0]
        connection.execute(insert(squads).values(id=squad_id, country=squad['country'],
                           tournament=squad['tournament'], sort_order=int(squad_id))
                           .on_conflict_do_nothing(index_elements=['id']))
        connection.execute(insert(players).values([
            dict(id=p['id'], squad_id=squad_id, name=p['name'], role=p['role'],
                 rating=p['rating'], sort_order=int(p['id'].split('-')[1]))
            for p in squad['players']
        ]).on_conflict_do_nothing(index_elements=['id']))


def downgrade():
    connection = op.get_bind()
    connection.execute(sa.text('SELECT pg_advisory_xact_lock(734829106)'))
    snapshot = data()
    connection.execute(players.delete().where(players.c.id.in_([p['id'] for s in snapshot for p in s['players']])))
    # Existing classic squads only received extra players; keep those squads intact.
    connection.execute(squads.delete().where(squads.c.id.in_([
        s['players'][0]['id'].split('-')[0] for s in snapshot if s['newSquad']
    ])))
