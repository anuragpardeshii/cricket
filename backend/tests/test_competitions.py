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


def test_recent_rolls_prefer_different_historical_squads(monkeypatch):
    squads=[]
    for index in range(4):
        player=dict(id=f'x{index}',name=f'Player {index}',role='BAT',rating=80,
                    squad=f'TEAM {index} 2024',competition='t20',edition=2024)
        squads.append(dict(country=f'TEAM {index}',tournament='T20 WORLD CUP 2024',players=[player]))
    monkeypatch.setattr(rooms.rng,'choice',lambda values:values[0])
    practice=game.initial()
    practice_rolls=[]
    for _ in range(4):
        game.act(practice,'roll',squads=squads)
        practice_rolls.append(practice['rolled']['players'][0]['squad'])
    assert len(set(practice_rolls))==4

    state=rooms.new_state('host',SimpleNamespace(name='Host',capacity=2,format='knockout',pick_seconds=30,competition='t20'))
    state['members'][0]['ready']=True; rooms.start(state,100)
    players=[squad['players'][0] for squad in squads]
    options=[dict(player=player,slot='n3') for player in players]
    room_rolls=[]
    for number in range(4):
        rooms.roll(state,players,options,ts=101+number)
        room_rolls.append(state['rolled']['players'][0]['squad'])
    assert len(set(room_rolls))==4


def test_match_length_follows_competition(monkeypatch):
    class StableRandom:
        def choice(self,values): return values[0]
        def choices(self,_values,_weights): return [1]
        def random(self): return .5
    monkeypatch.setattr(game,'rng',StableRandom())
    roles=['OP','OP','BAT','BAT','BAT','AR','WK','PACE','PACE','PACE','SPIN']
    slots=['op1','op2','n3','n4','n5','ar','wk','b1','b2','b3','b4']
    team=lambda prefix:{slot:dict(id=f'{prefix}-{index}',name=f'{prefix}{index}',role=role,rating=80,squad='TEST 2024') for index,(slot,role) in enumerate(zip(slots,roles))}
    odi=game.simulate(team('a'),team('b'),overs=game.match_overs('odi'))
    t20=game.simulate(team('c'),team('d'),overs=game.match_overs('t20'))
    assert odi['overs']==50 and len(odi['timeline'])==100
    assert t20['overs']==20 and len(t20['timeline'])==40
    assert all(card['score'].endswith('(50.0)') for card in odi['scorecards'])
