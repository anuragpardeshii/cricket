"""Persist the existing tournament catalog, preserving all draft player IDs."""
import json
from pathlib import Path
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    squads = op.create_table(
        'squads',
        sa.Column('id', sa.String(16), primary_key=True),
        sa.Column('country', sa.String(64), nullable=False),
        sa.Column('tournament', sa.String(80), nullable=False),
        sa.Column('sort_order', sa.Integer, nullable=False),
        sa.CheckConstraint('sort_order >= 0'),
    )
    players = op.create_table(
        'players',
        sa.Column('id', sa.String(16), primary_key=True),
        sa.Column('squad_id', sa.String(16), sa.ForeignKey('squads.id'), nullable=False),
        sa.Column('name', sa.String(80), nullable=False),
        sa.Column('role', sa.String(8), nullable=False),
        sa.Column('rating', sa.Integer, nullable=False),
        sa.Column('sort_order', sa.Integer, nullable=False),
        sa.CheckConstraint('rating BETWEEN 1 AND 100'),
        sa.CheckConstraint("role IN ('OP','BAT','AR','WK','PACE','SPIN')"),
        sa.CheckConstraint('sort_order >= 0'),
    )
    op.create_index('ix_players_squad_id', 'players', ['squad_id'])
    # Frozen migration input: future application catalog changes cannot alter this migration.
    data = json.loads((Path(__file__).resolve().parents[1] / 'data/catalog_v1.json').read_text())
    for order, squad in enumerate(data['squads']):
        squad_id = squad['players'][0]['id'].split('-')[0]
        op.bulk_insert(squads, [dict(id=squad_id, country=squad['country'], tournament=squad['tournament'], sort_order=order)])
        op.bulk_insert(players, [dict(id=p['id'], squad_id=squad_id, name=p['name'], role=p['role'], rating=p['rating'], sort_order=i) for i, p in enumerate(squad['players'])])
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname='out_app') THEN
        GRANT SELECT ON squads, players TO out_app;
    END IF; END $$""")


def downgrade():
    op.drop_table('players')
    op.drop_table('squads')
