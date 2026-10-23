"""Database catalog, serialized in the existing frontend contract."""
import json
from pathlib import Path
from fastapi import HTTPException
from sqlalchemy import select
from .db import PlayerRecord, SquadRecord

# Slot compatibility is a game rule, not player inventory.
SLOTS = json.loads(Path(__file__).with_name('catalog.json').read_text())['slots']


def load_catalog(session):
    rows = session.execute(
        select(SquadRecord, PlayerRecord)
        .join(PlayerRecord, PlayerRecord.squad_id == SquadRecord.id)
        .order_by(SquadRecord.sort_order, SquadRecord.id, PlayerRecord.sort_order, PlayerRecord.id)
    )
    squads = {}
    for squad, player in rows:
        item = squads.setdefault(squad.id, dict(country=squad.country, tournament=squad.tournament, players=[]))
        item['players'].append(dict(id=player.id, name=player.name, role=player.role, rating=player.rating,
                                   squad=f'{squad.country} {squad.tournament[-4:]}'))
    if not squads:
        raise HTTPException(503, 'Player catalog unavailable')
    return dict(squads=list(squads.values()), slots=SLOTS)
