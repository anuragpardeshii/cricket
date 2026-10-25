"""Database catalog, serialized in the existing frontend contract."""
import json
import os
from pathlib import Path
from threading import RLock
from fastapi import HTTPException
from sqlalchemy import select
from .db import PlayerRecord, SquadRecord
from .draft_pool import competition, person_key

# Slot compatibility is a game rule, not player inventory.
SLOTS = json.loads(Path(__file__).with_name('catalog.json').read_text())['slots']
_CACHE = {}
_CACHE_LOCK = RLock()


def clear_catalog_cache():
    """Clear process-local catalog data after maintenance or in focused tests."""
    with _CACHE_LOCK:
        _CACHE.clear()


def cache_enabled():
    # Production inventory changes only through a deploy-time migration. Avoid
    # caching in tests/development, where catalog rows can be edited in-place.
    return os.getenv('APP_ENV') == 'production'


def load_catalog(session, selected=None, edition=None):
    key = (selected, edition)
    if cache_enabled():
        with _CACHE_LOCK:
            if key in _CACHE:
                return _CACHE[key]
    query = (
        select(SquadRecord, PlayerRecord)
        .join(PlayerRecord, PlayerRecord.squad_id == SquadRecord.id)
        .order_by(SquadRecord.sort_order, SquadRecord.id, PlayerRecord.sort_order, PlayerRecord.id)
    )
    # Fetch only the selected pool: the archive spans hundreds of squads.
    prefix={'odi':'WORLD CUP ', 't20':'T20 WORLD CUP ', 'ipl':'IPL '}.get(selected)
    if prefix and edition is not None:
        query=query.where(SquadRecord.tournament==f'{prefix}{edition}')
    elif prefix:
        query=query.where(SquadRecord.tournament.startswith(prefix))
    elif edition is not None:
        query=query.where(SquadRecord.tournament.endswith(str(edition)))
    rows=session.execute(query)
    squads = {}
    for squad, player in rows:
        item = squads.setdefault(squad.id, dict(country=squad.country, tournament=squad.tournament, players=[]))
        item['players'].append(dict(id=player.id, name=player.name, role=player.role, rating=player.rating,
                                   squad=f'{squad.country} {squad.tournament[-4:]}', competition=competition(squad.tournament),
                                   edition=int(squad.tournament[-4:])))
        item['players'][-1]['personId']=person_key(item['players'][-1])
    if not squads:
        raise HTTPException(503, 'Player catalog unavailable')
    result = dict(squads=list(squads.values()), slots=SLOTS)
    if cache_enabled():
        with _CACHE_LOCK:
            # Another request may have populated the same immutable pool while
            # this query was running. Reuse the first completed value.
            result = _CACHE.setdefault(key, result)
    return result
