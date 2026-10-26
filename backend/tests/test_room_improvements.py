import copy
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import rooms
from app.catalog import SLOTS
from app.db import Room, Session
from app.main import app
from test_preflight import clean, client, ready_room, room_for


def test_readiness_is_personal_required_and_can_be_withdrawn():
    a,b,outsider=[client(n) for n in ['alice','bob','eve']]
    room=room_for(a,4); path=f"/api/rooms/{room['id']}"
    assert all(not m['ready'] for m in room['state']['members'])
    assert a.post(path+'/actions',json={'action':'start','version':room['version']}).status_code==409
    room=ready_room(a,room)
    # A later join introduces an unready player, even though the host was ready.
    room=b.post('/api/rooms/join',json={'code':room['code']}).json()
    assert [m['ready'] for m in room['state']['members']]==[True,False]
    assert a.post(path+'/actions',json={'action':'start','version':room['version']}).status_code==409
    assert outsider.post(path+'/ready',json={'ready':True}).status_code==404
    assert b.post(path+'/ready',json={'ready':True,'member_id':room['state']['members'][0]['id']}).status_code==422
    assert b.post(path+'/ready',json={'ready':True},headers={'x-csrf-token':'wrong'}).status_code==403
    room=ready_room(a,room,b)
    again=b.post(path+'/ready',json={'ready':True}).json()
    assert again['version']==room['version'] # Idempotent retries.
    room=b.post(path+'/ready',json={'ready':False}).json()
    assert a.post(path+'/actions',json={'action':'start','version':room['version']}).status_code==409
    room=ready_room(a,room,b)
    assert b.post(path+'/actions',json={'action':'start','version':room['version']}).status_code==403
    response=a.post(path+'/actions',json={'action':'start','version':room['version']})
    assert response.status_code==200,response.text
    assert sum(m['is_ai'] for m in response.json()['state']['members'])==2
    assert b.post(path+'/ready',json={'ready':False}).status_code==409


def test_lobby_host_transfers_and_last_exit_deletes_room():
    a,b=client(),client('bob')
    room=room_for(a,2); room=b.post('/api/rooms/join',json={'code':room['code']}).json()
    first=a.post(f"/api/rooms/{room['id']}/exit",json={})
    assert first.status_code==200 and first.json()=={'ok':True,'closed':False}
    transferred=b.get(f"/api/rooms/{room['id']}")
    assert transferred.status_code==200 and transferred.json()['host'] is True
    last=b.post(f"/api/rooms/{room['id']}/exit",json={})
    assert last.status_code==200 and last.json()=={'ok':True,'closed':True}
    assert b.get(f"/api/rooms/{room['id']}").status_code==404
    with Session() as session: assert session.get(Room,room['id']) is None


def test_expired_join_window_cannot_start_even_a_ready_room():
    a=client(); room=ready_room(a,room_for(a,2))
    with Session.begin() as session:
        row=session.get(Room,room['id']); state=copy.deepcopy(row.state)
        state['lobbyDeadline']=time.time()-1000; row.state=state
    rooms.tick()
    assert a.get(f"/api/rooms/{room['id']}").json()['state']['phase']=='lobby'


def test_draft_revision_ignores_other_teams_formation_but_rejects_replays():
    a=client(); b=client('bob'); room=room_for(a,2)
    b.post('/api/rooms/join',json={'code':room['code']})
    room=ready_room(a,room,b); path=f"/api/rooms/{room['id']}/actions"
    room=a.post(path,json={'action':'start','version':room['version']}).json()
    stale=room
    change=b.post(path,json={'action':'formation','version':room['version'],'order':[s['id'] for s in SLOTS][::-1]})
    assert change.status_code==200
    roll={'action':'roll','version':stale['version'],'draft_revision':stale['state']['draftRevision']}
    response=a.post(path,json=roll); assert response.status_code==200,response.text
    room=response.json()
    assert a.post(path,json={**roll,'version':room['version']}).status_code==409
    assert a.post(path,json={**roll,'draft_revision':99999}).status_code==409
    assert b.post(path,json={'action':'formation','version':room['version'],'order':[s['id'] for s in SLOTS]}).status_code==200
    player,slots=next(iter(room['state']['rolled']['allowedSlots'].items()))
    payload={'action':'pick','version':room['version'],'draft_revision':room['state']['draftRevision'],'player_id':player,'slot_id':slots[0]}
    def pick(_):
        with TestClient(app,headers=dict(a.headers),cookies=dict(a.cookies)) as other:
            return other.post(path,json=payload).status_code
    with ThreadPoolExecutor(max_workers=2) as pool: statuses=list(pool.map(pick,range(2)))
    assert sorted(statuses)==[200,409]
    visible=b.get(f"/api/rooms/{room['id']}").json()
    assert visible['state']['taken']==[player]
    assert visible['state']['turn']==0 and visible['state']['turnPicks']==1


def reference_eligible(state,players):
    """Deliberately slow inventory check, independent of reserve subtraction."""
    current=state['members'][state['turn']]; result=[]
    groups=[({'OP'},{'op1','op2'}),({'OP','BAT'},{'op1','op2','n3','n4','n5'}),({'AR'},{'ar'}),({'WK'},{'wk'}),({'PACE','SPIN'},{'b1','b2','b3','b4'})]
    for p in players:
        if p['id'] in state['taken']: continue
        for slot in SLOTS:
            if slot['id'] in current['xi'] or p['role'] not in slot['accepts']: continue
            remaining=[s for m in state['members'] for s in SLOTS if s['id'] not in m['xi'] and not (m is current and s['id']==slot['id'])]
            available=[q for q in players if q['id'] not in state['taken'] and q['id']!=p['id']]
            if all(sum(q['role'] in roles for q in available)>=sum(s['id'] in slots for s in remaining) for roles,slots in groups):
                result.append((p['id'],slot['id']))
    return result


def test_eight_team_draft_reserves_remain_equivalent_and_projection_is_detached():
    players=[p for s in json.loads((Path(rooms.__file__).parent/'catalog.json').read_text())['squads'] if s['tournament']=='WORLD CUP 2023' for p in s['players']]
    # This legacy reference counts cards; give each card its own identity here.
    players=[dict(p,id='reference-'+p['id'],personId='reference-'+p['id']) for p in players]
    state=rooms.new_state('host',SimpleNamespace(name='Host',capacity=8,format='league',pick_seconds=30,lobby_minutes=5))
    state['members'][0]['ready']=True; rooms.start(state,1000)
    for pick_number in range(88):
        if pick_number%11==0:
            assert [(o['player']['id'],o['slot']) for o in rooms.eligible(state,players)]==reference_eligible(state,players)
        rooms.pick(state,players,1000+pick_number,automatic=True)
    assert len(set(state['taken']))==88
    assert all(len(m['xi'])==11 for m in state['members'])
    row=SimpleNamespace(state=state,id='test',code='TEST',visibility='private',version=1,owner_id='host')
    saved=copy.deepcopy(state)
    visible=rooms.project(row,'host',1090)
    assert all('plan' not in m and 'winner' not in m for m in visible['state']['matches'])
    visible['state']['members'][0]['xi'].clear()
    assert state==saved
    rooms.advance(state,players,10000)
    result=rooms.project(row,'host',10000)
    result['state']['matches'][0]['scorecards'][0]['batting'][0]['runs']=-1
    assert state['matches'][0]['plan']['scorecards'][0]['batting'][0]['runs']>=0


def test_clock_skips_locked_room_and_advances_another():
    a=client(); first=ready_room(a,room_for(a,2)); second=ready_room(a,room_for(a,2))
    for room in [first,second]:
        assert a.post(f"/api/rooms/{room['id']}/actions",json={'action':'start','version':room['version']}).status_code==200
        with Session.begin() as session:
            row=session.get(Room,room['id']); state=copy.deepcopy(row.state)
            state['deadline']=time.time()-1; row.state=state
    from sqlalchemy import select
    with Session.begin() as session:
        locked=session.scalar(select(Room).where(Room.id==first['id']).with_for_update())
        rooms.tick()
        assert locked.state['taken']==[]
        assert len(a.get(f"/api/rooms/{second['id']}").json()['state']['taken'])==1
