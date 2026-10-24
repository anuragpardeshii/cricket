import copy
import importlib.util
import json
import pytest
from pathlib import Path

from sqlalchemy import delete, select, update

from app import game, rooms
from app.catalog import load_catalog
from app.db import Game, PlayerRecord, SquadRecord, Session, engine
from test_preflight import clean, client, create, action

ROOT = Path(__file__).resolve().parents[1]
CARD_COUNT = sum(len(s['players']) for s in json.loads((ROOT/'app/catalog.json').read_text())['squads'])


def test_expanded_catalog_keeps_original_cards_and_matches_database():
    original=json.loads((ROOT/'migrations/data/catalog_v1.json').read_text())
    additions=json.loads((ROOT/'migrations/data/catalog_v2.json').read_text())['squads']
    current=json.loads((ROOT/'app/catalog.json').read_text())
    for old,now in zip(original['squads'],current['squads']):
        assert old['country']==now['country'] and old['tournament']==now['tournament']
        assert now['players'][:len(old['players'])]==old['players']
    assert current['squads'][9:24]==additions
    assert len(additions)==15 and all(len(s['players'])==15 for s in additions)
    assert len({(s['country'],s['tournament']) for s in current['squads']})==431
    cards=[p for s in current['squads'] for p in s['players']]
    assert len(cards)==len({p['id'] for p in cards})==CARD_COUNT
    from app.draft_pool import PLAYER_IDENTITIES
    assert set(PLAYER_IDENTITIES)=={p['id'] for p in cards}
    assert all(1<=p['rating']<=100 and p['role'] in {'OP','BAT','AR','WK','PACE','SPIN'} for p in cards)
    for squad in additions:
        assert len({p['name'] for p in squad['players']})==15
        assert all(p['squad']==f"{squad['country']} {squad['tournament'][-4:]}" for p in squad['players'])
    def without_metadata(catalog):
        for squad in catalog['squads']:
            for p in squad['players']: p.pop('personId',None); p.pop('competition',None); p.pop('edition',None)
        return catalog
    with Session() as session:
        assert without_metadata(load_catalog(session))==current
    assert without_metadata(client().get('/api/catalog').json())==current


@pytest.mark.parametrize('filename',['0009_more_tournament_squads.py','0011_historical_editions.py','0012_complete_tournament_archive.py'])
def test_expansion_upgrade_is_idempotent_and_keeps_saved_games(monkeypatch,filename):
    spec=importlib.util.spec_from_file_location('catalog_expansion',ROOT/'migrations/versions'/filename)
    migration=importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    snapshot=migration.data()
    removed_squads=sum(s.get('newSquad',True) for s in snapshot)
    removed_cards=sum(len(s['players']) for s in snapshot)
    first,second=[p['id'] for s in snapshot for p in s['players']][:2]
    c=client(); saved=action(c,create(c),'roll').json()
    with engine.connect() as connection:
        transaction=connection.begin()
        try:
            monkeypatch.setattr(migration.op,'get_bind',lambda:connection)
            original_state=copy.deepcopy(connection.scalar(select(Game.state).where(Game.id==saved['id'])))
            migration.downgrade()
            assert len(connection.execute(select(SquadRecord.id)).all())==431-removed_squads
            assert len(connection.execute(select(PlayerRecord.id)).all())==CARD_COUNT-removed_cards
            connection.execute(update(PlayerRecord).where(PlayerRecord.id=='0-0').values(rating=99))
            migration.upgrade(); migration.upgrade()
            assert len(connection.execute(select(SquadRecord.id)).all())==431
            assert len(connection.execute(select(PlayerRecord.id)).all())==CARD_COUNT
            assert connection.scalar(select(PlayerRecord.rating).where(PlayerRecord.id=='0-0'))==99
            # A partially restored catalog is repaired without overwriting edits.
            connection.execute(update(PlayerRecord).where(PlayerRecord.id==first).values(rating=99))
            connection.execute(delete(PlayerRecord).where(PlayerRecord.id==second))
            migration.upgrade()
            assert connection.scalar(select(PlayerRecord.rating).where(PlayerRecord.id==first))==99
            assert connection.scalar(select(PlayerRecord.id).where(PlayerRecord.id==second))==second
            assert connection.scalar(select(Game.state).where(Game.id==saved['id']))==original_state
        finally:
            transaction.rollback()


def test_each_added_squad_can_be_rolled_and_picked_in_practice_and_rooms(monkeypatch):
    from types import SimpleNamespace
    with Session() as session: catalog=load_catalog(session)
    from app.draft_pool import competition
    for squad in catalog['squads'][9:]:
        label=squad['players'][0]['squad']
        selected=competition(squad['tournament']); edition=int(squad['tournament'][-4:])
        pool=[s for s in catalog['squads'] if s['tournament']==squad['tournament']]
        players=[p for s in pool for p in s['players']]
        # Force each new squad through the real eligibility and pick rules.
        monkeypatch.setattr(game.rng,'choice',lambda candidates:next(x for x in candidates if (x['country']+' '+x['tournament'][-4:])==label) if isinstance(candidates[0],dict) else label)
        practice=game.initial(selected,edition)
        game.act(practice,'roll',squads=pool)
        assert practice['rolled']==squad
        player=squad['players'][0]
        slot=next(s['id'] for s in catalog['slots'] if player['role'] in s['accepts'])
        game.act(practice,'pick',player['id'],slot,squads=pool)
        assert practice['yourXI'][slot]==player
        state=rooms.new_state('host',SimpleNamespace(name='Host',capacity=8,format='league',pick_seconds=30,lobby_minutes=5,competition=selected,edition=edition))
        state['members'][0]['ready']=True; rooms.start(state,100)
        rooms.roll(state,players,ts=101)
        assert {p['id'] for p in state['rolled']['players']}=={p['id'] for p in squad['players']}
        rooms.pick(state,players,102,player['id'],slot)
        assert state['members'][0]['xi'][slot]==player


def test_all_previously_published_cards_are_preserved():
    current=json.loads((ROOT/'app/catalog.json').read_text())
    cards={p['id']:p for s in current['squads'] for p in s['players']}
    for version in range(1,5):
        frozen=json.loads((ROOT/f'migrations/data/catalog_v{version}.json').read_text())
        for squad in frozen['squads']:
            for player in squad['players']:
                assert cards[player['id']]==player
