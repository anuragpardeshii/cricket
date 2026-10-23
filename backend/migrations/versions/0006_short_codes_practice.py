"""Four-character online room codes; practice games have no invitation code."""
from alembic import op
import sqlalchemy as sa
import secrets
revision='0006'
down_revision='0005'
branch_labels=None
depends_on=None

def upgrade():
    connection=op.get_bind()
    op.execute('LOCK TABLE rooms IN ACCESS EXCLUSIVE MODE')
    rows=connection.execute(sa.text('SELECT id, code FROM rooms ORDER BY id')).all()
    used={r.code for r in rows if len(r.code)==4}
    for row in rows:
        if len(row.code)==4: continue
        while True:
            code=''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(4))
            if code not in used: break
        used.add(code)
        connection.execute(sa.text('UPDATE rooms SET code=:code WHERE id=:id'),dict(code=code,id=row.id))
    op.alter_column('rooms','code',type_=sa.String(4),existing_nullable=False)
    op.create_check_constraint('ck_rooms_code','rooms',"code ~ '^[A-Z2-9]{4}$'")
    op.alter_column('games','code',existing_type=sa.String(8),nullable=True)
    op.execute("UPDATE games SET state=jsonb_set(state, '{screen}', '\"draft\"') WHERE state->>'screen'='lobby'")

def downgrade():
    op.drop_constraint('ck_rooms_code','rooms',type_='check')
    op.alter_column('rooms','code',type_=sa.String(8),existing_nullable=False)
    op.execute("UPDATE rooms SET code=code || 'AAAA' WHERE char_length(code)=4")
    connection=op.get_bind()
    used=set(connection.execute(sa.text('SELECT code FROM games WHERE code IS NOT NULL')).scalars())
    for game_id in connection.execute(sa.text('SELECT id FROM games WHERE code IS NULL')).scalars():
        while True:
            code=''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(8))
            if code not in used: break
        used.add(code)
        connection.execute(sa.text('UPDATE games SET code=:code WHERE id=:id'),dict(code=code,id=game_id))
    op.alter_column('games','code',existing_type=sa.String(8),nullable=False)
