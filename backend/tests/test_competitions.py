import copy
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import game, rooms
from app.catalog import load_catalog, SLOTS
from app.draft_pool import person_key, eligible_picks
from app.db import Session
from test_preflight import clean, client, ready_room


@pytest.mark.parametrize('competition,squad_count',[('odi',113),('t20',152),('ipl',166)])
def test_eight_unique_teams_can_finish_each_competition(competition,squad_count,monkeypatch):
    with Session() as session: catalog=load_catalog(session)
    players=[p for s in catalog['squads'] for p in s['players']]
    assert len({p['squad'] for p in players if p['competition']==competition})==squad_count
    state=rooms.new_state('host',SimpleNamespace(name='Host',capacity=8,format='knockout',pick_seconds=30,competition=competition))
    state['members'][0]['ready']=True; rooms.start(state,1000)
    # Validate draft completion separately from simulation (covered by match tests).
    monkeypatch.setattr(rooms,'fixtures',lambda *_:None)
    for turn in range(88):
        rooms.roll(state,players,ts=1000+turn)
        assert all(p['competition']==competition for p in state['rolled']['players'])
        rooms.pick(state,players,1000+turn,automatic=True)
    picked=[p for m in state['members'] for p in m['xi'].values()]
    assert len(picked)==len({person_key(p) for p in picked})==88
    assert state['phase']=='live'
    assert all(p['competition']==competition for p in picked)


def test_person_identity_blocks_other_editions_and_distinguishes_namesakes():
    with Session() as session: players=[p for s in load_catalog(session)['squads'] for p in s['players']]
    kohlis=[p for p in players if p['name']=='V Kohli']
    state=rooms.new_state('host',SimpleNamespace(name='Host',capacity=2,format='knockout',pick_seconds=30))
    state['members'][0]['ready']=True; rooms.start(state,100)
    state['members'][0]['xi']['n3']=kohlis[0]; state['taken']=[kohlis[0]['id']]
    assert not any(o['player']['name']=='V Kohli' for o in rooms.eligible(state,players))
    practice=game.initial(); practice['opponentXI']['n3']=kohlis[0]
    assert all(not game.fits(practice,p) for p in players if person_key(p)==person_key(kohlis[0]))
    assert len({person_key(p) for p in players if p['name']=='I Ahmed'})==2
    assert len({person_key(p) for p in players if p['name']=='A Khan'})==2


def test_mixed_role_editions_reserve_people_not_card_counts():
    # Two openers remain. The sole other opener also has a batting-only edition.
    # Picking that edition in n3 would make the two remaining opener slots impossible.
    def p(id,name,role):return dict(id=id,name=name,role=role,rating=80,squad='TEST 2024')
    current={s['id']:p(s['id'],s['id'],'PACE') for s in SLOTS if s['id'] not in ['op1','op2','n3']}
    pool=[p('x1','X','OP'),p('x2','X','BAT'),p('y','Y','OP'),p('z','Z','BAT')]
    options={(o['player']['id'],o['slot']) for o in eligible_picks([current],current,pool,SLOTS)}
    assert ('x2','n3') not in options and ('x1','n3') not in options
    assert {('x1','op1'),('y','op2'),('z','n3')}<=options


def test_random_fixture_draw_preserves_bracket_and_every_league_pair(monkeypatch):
    members=[dict(id=str(i)) for i in range(4)]
    monkeypatch.setattr(rooms.rng,'shuffle',lambda values:values.__setitem__(slice(None),values[2:]+values[:2][::-1]))
    monkeypatch.setattr(rooms,'launch_ready',lambda *_:None)
    for format in ['knockout','league']:
        state=dict(members=members,format=format)
        rooms.fixtures(state,0)
        if format=='knockout':
            opening=[m for m in state['matches'] if m['round']==1]
            assert [(m['a'],m['b']) for m in opening]==[('2','3'),('1','0')]
            assert state['matches'][-1]['sources']==[m['id'] for m in opening]
        else:
            pairs={frozenset([m['a'],m['b']]) for m in state['matches']}
            assert len(pairs)==6 and all(len(pair)==2 for pair in pairs)
    assert members==[dict(id=str(i)) for i in range(4)]


def test_roll_is_private_and_competition_is_validated():
    a,b=client(),client('bob')
    settings=dict(format='knockout',capacity=2,pick_seconds=30,competition='ipl')
    assert a.post('/api/rooms',json={**settings,'competition':'unknown'}).status_code==422
    room=a.post('/api/rooms',json=settings).json(); path=f"/api/rooms/{room['id']}"
    b.post('/api/rooms/join',json={'code':room['code']}); room=ready_room(a,room,b)
    room=a.post(path+'/actions',json={'action':'start','version':room['version']}).json()
    room=a.post(path+'/actions',json={'action':'roll','version':room['version']}).json()
    assert room['state']['rolled']['players']
    assert all(p['competition']=='ipl' for p in room['state']['rolled']['players'])
    assert b.get(path).json()['state']['rolled'] is None
    assert 'lobbyDeadline' not in room['state']
