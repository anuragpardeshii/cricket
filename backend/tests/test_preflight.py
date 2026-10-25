"""Destructive fixtures are restricted to an isolated *_test PostgreSQL database."""
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text, select
from app.main import app, Session, Game, User, LoginSession, Audit, digest, COOKIE
from app.db import engine
from app.game import SLOTS
HEADERS={'origin':'http://localhost:5173','x-out-request':'1'}
@pytest.fixture(autouse=True)
def clean():
    assert engine.url.database.endswith('_test'), 'Refusing to reset a non-test database'
    with engine.begin() as connection:
        connection.execute(text('TRUNCATE users, sessions, games, audit_events, rate_buckets CASCADE'))
def client(name='alice'):
    c=TestClient(app,headers=HEADERS)
    response=c.post('/api/auth/register',json=dict(username=name,email=name+'@example.com',phone=str(int.from_bytes(name.encode(),'big') % 10000000000).zfill(10),password='a distinct long passphrase '+name))
    assert response.status_code==201,response.text
    c.headers['x-csrf-token']=response.json()['csrf']
    return c
def create(c):
    response=c.post('/api/games',json={}); assert response.status_code==201,response.text
    return response.json()
def action(c,g,act,**kw): return c.post(f"/api/games/{g['id']}/actions",json=dict(action=act,version=g['version'],**kw))
def finish_ai(c,g):
    # Advance only the isolated test game's clock; production waits three seconds.
    import copy, time
    with Session.begin() as session:
        game=session.get(Game,g['id']); state=copy.deepcopy(game.state)
        assert state['turn']=='opp'
        state['aiDeadline']=time.time()-1; game.state=state
    response=c.get(f"/api/games/{g['id']}")
    assert response.status_code==200,response.text
    return response.json()

def test_auth_csrf_sensitive_data_and_logout():
    c=client(); token=c.cookies.get(COOKIE)
    assert 'httponly' in c.post('/api/auth/login',json={'email':'alice@example.com','password':'a distinct long passphrase alice'}).headers['set-cookie'].lower()
    me=c.get('/api/auth/me'); c.headers['x-csrf-token']=me.json()['csrf']
    assert set(me.json()['user'])=={'id','username','is_admin'}
    with Session() as s:
        assert s.scalar(select(User)).password_hash.startswith('$argon2id$')
        assert s.get(LoginSession,digest(token)) is None
    assert c.post('/api/games',json={},headers={'origin':'https://evil.example'}).status_code==403
    assert c.post('/api/games',json={},headers={'x-csrf-token':'wrong'}).status_code==403
    assert c.post('/api/auth/logout',json={}).status_code==200
    assert c.get('/api/games').status_code==401
    assert TestClient(app).get('/api/games').status_code==401

def test_idor_and_mass_assignment():
    a=client(); b=client('bob'); g=create(a)
    assert b.get(f"/api/games/{g['id']}").status_code==404
    assert action(b,g,'start').status_code==404
    assert action(a,g,'start',owner_id='bob').status_code==422
    assert action(a,g,'start',version_override=999).status_code==422

def test_validation_and_injection():
    c=TestClient(app,headers=HEADERS)
    data=dict(username="<script>alert(1)</script>",email='x@example.com',phone='1234567890',password='an adequately long password')
    assert c.post('/api/auth/register',json=data).status_code==422
    data['username']='valid'; data['role']='admin'
    assert c.post('/api/auth/register',json=data).status_code==422
    response=c.post('/api/auth/login',json={'email':"' OR 1=1 --",'password':'secret'})
    assert response.status_code==422 and 'secret' not in response.text
    assert c.post('/api/auth/login',content='x'*17000,headers={'content-type':'application/json'}).status_code==413
    assert c.post('/api/auth/login',content='email=x').status_code==415

@pytest.mark.parametrize('password,status', [('Abc12!',422),('Abc123!',201),('Abc123!x',201),('aaaaaaa',422),('😀abcd!',422),('😀abc12!',201)])
def test_registration_password_minimum_seven_characters(password,status):
    c=TestClient(app,headers=HEADERS)
    data=dict(username='lengthcheck',email='lengthcheck@example.com',phone='9876543210',password=password)
    response=c.post('/api/auth/register',json=data)
    assert response.status_code==status,response.text
    if status==201:
        assert c.post('/api/auth/login',json={'email':data['email'],'password':password}).status_code==200

def test_draft_inventory_replay_and_complete_match():
    c=client(); g=create(c)
    assert action(c,g,'match').status_code==409
    old=g
    g=action(c,g,'roll').json()
    assert action(c,old,'roll').status_code==409
    for _ in range(3): g=action(c,g,'roll').json()
    assert action(c,g,'roll').status_code==409
    assert action(c,g,'pick',player_id='forged',slot_id='op1').status_code==409
    used=[]
    for _ in range(11):
        if not g['state']['rolled']: g=action(c,g,'roll').json()
        pair=next((p,s) for p in g['state']['rolled']['players'] for s in SLOTS if s['id'] not in g['state']['yourXI'] and p['role'] in s['accepts'])
        p,slot=pair; used.append(p['id'])
        g=finish_ai(c,action(c,g,'pick',player_id=p['id'],slot_id=slot['id']).json())
    assert len(set(used))==11
    assert g['opponentCount']==11
    assert all(p and p['id'] for p in g['state']['opponentXI'].values())
    g=action(c,g,'match').json()
    assert g['state']['match']['result']['winner'] in ('you','opp','tie')
    both=list(g['state']['yourXI'].values())+list(g['state']['opponentXI'].values())
    assert len({p['id'] for p in both})==22
    again=action(c,g,'match').json()
    assert again['state']['match']==g['state']['match']
    assert c.get('/api/dashboard').status_code==403
    with Session.begin() as session:
        session.scalar(select(User).where(User.username=='alice')).is_admin=True
    assert c.get('/api/admin/analytics').json()['matchesFinished']==1
    with Session() as s: assert len(list(s.scalars(select(Audit))))>=25

def test_concurrent_mutations_one_winner():
    c=client(); g=create(c)
    # Separate HTTP clients share credentials, not in-memory request state.
    def mutate(_):
        with TestClient(app,headers=dict(c.headers),cookies=dict(c.cookies)) as other:
            return action(other,g,'roll').status_code
    with ThreadPoolExecutor(max_workers=2) as pool: statuses=list(pool.map(mutate,range(2)))
    assert sorted(statuses)==[200,409]
    with Session() as s: assert s.get(Game,g['id']).version==1

def test_auth_rate_limit_and_headers():
    c=TestClient(app,headers=HEADERS)
    for _ in range(10): assert c.post('/api/auth/login',json={'email':'missing@example.com','password':'incorrect'}).status_code==401
    assert c.post('/api/auth/login',json={'email':'missing@example.com','password':'incorrect'}).status_code==429
    response=c.get('/api/health')
    assert response.headers['cache-control']=='no-store'
    assert response.headers['x-content-type-options']=='nosniff'
    assert TestClient(app,base_url='http://evil.example').get('/api/health').status_code==400

def test_expired_session_and_audit_immutability():
    from datetime import timedelta
    from app.db import now
    from sqlalchemy.exc import DBAPIError
    c=client()
    with Session.begin() as s:
        auth=s.get(LoginSession,digest(c.cookies.get(COOKIE)))
        auth.expires=now()-timedelta(seconds=1)
    assert c.get('/api/auth/me').status_code==401
    with pytest.raises(DBAPIError):
        with engine.begin() as connection: connection.execute(text("UPDATE audit_events SET action='tampered'"))

def test_concurrent_pick_is_not_duplicated():
    c=client(); g=create(c); g=action(c,g,'roll').json()
    p,slot=next((p,s) for p in g['state']['rolled']['players'] for s in SLOTS if p['role'] in s['accepts'])
    def pick(_):
        with TestClient(app,headers=dict(c.headers),cookies=dict(c.cookies)) as other:
            return action(other,g,'pick',player_id=p['id'],slot_id=slot['id']).status_code
    with ThreadPoolExecutor(max_workers=2) as pool: statuses=list(pool.map(pick,range(2)))
    assert sorted(statuses)==[200,409]
    final=finish_ai(c,c.get(f"/api/games/{g['id']}").json())
    assert len(final['state']['yourXI'])==1 and final['opponentCount']==1

def test_catalog_backfill_idempotent_and_preserves_saved_data():
    from app.backfill_players import backfill
    from app.catalog import load_catalog
    from app.db import PlayerRecord
    from sqlalchemy import update, delete
    c=client(); g=create(c); g=action(c,g,'roll').json()
    with engine.connect() as connection:
        transaction=connection.begin()
        try:
            saved_state=connection.scalar(select(Game.state).where(Game.id==g['id']))
            first=backfill(connection)
            assert first['inserted_players']==first['inserted_squads']==0
            connection.execute(update(PlayerRecord).where(PlayerRecord.id=='0-0').values(rating=99))
            connection.execute(delete(PlayerRecord).where(PlayerRecord.id=='0-1'))
            repaired=backfill(connection)
            assert repaired['inserted_players']==1 and repaired['inserted_squads']==0
            assert backfill(connection)['inserted_players']==0
            assert connection.scalar(select(PlayerRecord.rating).where(PlayerRecord.id=='0-0'))==99
            assert repaired['total_players']==first['total_players']
            with Session(bind=connection) as session:
                catalog=load_catalog(session)
                assert catalog['squads'][0]['players'][0]['rating']==99
            assert connection.scalar(select(Game.state).where(Game.id==g['id']))==saved_state
        finally: transaction.rollback()
    response=c.get('/api/catalog')
    assert response.status_code==200
    assert sum(len(s['players']) for s in response.json()['squads'])==first['total_players']

def test_guest_play_isolated_csrf_and_account_boundaries():
    a=TestClient(app,headers=HEADERS); b=TestClient(app,headers=HEADERS)
    for c in [a,b]:
        response=c.post('/api/auth/guest',json={})
        assert response.status_code==200 and response.json()['user'] is None
        assert response.json()['guest'] is True
        c.headers['x-csrf-token']=response.json()['csrf']
    g=create(a)
    assert b.get(f"/api/games/{g['id']}").status_code==404
    assert action(b,g,'start').status_code==404
    assert a.post(f"/api/games/{g['id']}/actions",json={'action':'start','version':0},headers={'x-csrf-token':''}).status_code==403
    for _ in range(11):
        g=action(a,g,'roll').json()
        p,slot=next((p,s) for p in g['state']['rolled']['players'] for s in SLOTS if s['id'] not in g['state']['yourXI'] and p['role'] in s['accepts'])
        g=finish_ai(a,action(a,g,'pick',player_id=p['id'],slot_id=slot['id']).json())
    assert action(a,g,'match').status_code==200
    assert a.get('/api/dashboard').status_code==403
    cookie=a.cookies.get(COOKIE)
    assert a.post('/api/auth/guest',json={}).json()['csrf']==a.headers['x-csrf-token']
    assert a.cookies.get(COOKIE)==cookie
    # A guest bootstrap must never replace a signed-in account.
    signed=client('signed')
    before=signed.get('/api/auth/me').json()
    assert signed.post('/api/auth/guest',json={}).json()==before
    assert signed.post('/api/auth/logout',json={}).status_code==200
    guest=signed.post('/api/auth/guest',json={}).json()
    assert guest['guest'] is True

def test_admin_guard_and_phone_constraints():
    c=client()
    assert c.get('/api/admin/analytics').status_code==403
    assert c.get('/api/dashboard').status_code==403
    data=dict(username='newperson',email='newperson@example.com',phone='12345678901',password='an excellent long passphrase',country_code='+91')
    assert c.post('/api/auth/register',json=data).status_code==422
    data['phone']='9876543210'; data['is_admin']=True
    assert c.post('/api/auth/register',json=data).status_code==422
    with Session.begin() as s: s.scalar(select(User).where(User.username=='alice')).is_admin=True
    assert c.get('/api/admin/analytics').status_code==200
    with Session.begin() as s: s.scalar(select(User).where(User.username=='alice')).is_admin=False
    assert c.get('/api/admin/analytics').status_code==403


def ready_room(host, room, *others):
    for person in (host, *others):
        response=person.post(f"/api/rooms/{room['id']}/ready",json={'ready':True})
        assert response.status_code==200,response.text
    return host.get(f"/api/rooms/{room['id']}").json()


def test_room_membership_turns_and_timeout():
    from app.db import Room
    from app import rooms
    import copy,time
    a=client(); b=client('bob'); outsider=client('eve')
    r=a.post('/api/rooms',json=dict(name='Alice',format='knockout',capacity=2,pick_seconds=10,lobby_minutes=5)).json()
    assert b.get(f"/api/rooms/{r['id']}").status_code==404
    r=b.post('/api/rooms/join',json=dict(name='Bob',code=r['code'])).json()
    assert outsider.post('/api/rooms/join',json=dict(name='Eve',code=r['code'])).status_code==409
    r=ready_room(a,r,b)
    payload=dict(action='start',version=r['version'])
    assert b.post(f"/api/rooms/{r['id']}/actions",json=payload).status_code==403
    r=a.post(f"/api/rooms/{r['id']}/actions",json=payload).json()
    assert b.post(f"/api/rooms/{r['id']}/actions",json=dict(action='pick',version=r['version'],player_id='0-0',slot_id='op1')).status_code==403
    old=r['version']
    with Session.begin() as session:
        row=session.get(Room,r['id']); state=copy.deepcopy(row.state); state['deadline']=time.time()-1; row.state=state
    rooms.tick()
    r=a.get(f"/api/rooms/{r['id']}").json()
    assert r['state']['lastPick']['automatic'] and len(r['state']['taken'])==1
    assert r['state']['turn']==1 and r['version']>old
    assert 'uid' not in r['state']['members'][0]
    assert outsider.get(f"/api/rooms/{r['id']}").status_code==404


def test_tournaments_scorecards_awards_and_future_redaction():
    from app import rooms
    from app.catalog import load_catalog
    from app.db import Room,uid
    from types import SimpleNamespace
    import time
    with Session() as session: players=[p for s in load_catalog(session)['squads'] for p in s['players']]
    for kind in ['knockout','league']:
        body=SimpleNamespace(format=kind,capacity=4,pick_seconds=10,lobby_minutes=5,name='One')
        state=rooms.new_state('one',body)
        for name in ['two','three','four']: state['members'].append(rooms.member(name,name))
        for m in state['members']: m['ready']=True
        ts=time.time(); rooms.start(state,ts)
        # All participants disconnect: the authoritative clock completes every turn.
        rooms.advance(state,players,ts+440)
        assert state['phase']=='live'
        assert len(set(state['taken']))==44
        row=Room(id=uid(),owner_id='one',code='TESTCODE',version=1,state=state)
        live=rooms.project(row,'one',ts+440)
        for match in live['state']['matches']:
            assert 'plan' not in match and 'winner' not in match and 'result' not in match
        rooms.advance(state,players,ts+10000)
        assert state['phase']=='complete' and state['champion'] and state['award']
        assert len(state['matches'])==(3 if kind=='knockout' else 6)
        if kind=='knockout':
            final=state['matches'][-1]
            assert {final['a'],final['b']}=={m['winner'] for m in state['matches'][:2]}
        for match in state['matches']:
            plan=match['plan']
            assert plan['result']['highestScorer'] and plan['result']['bestBowler']
            assert all(1<=len(e['deliveries'])<=6 for e in plan['timeline'])
            assert 2<=sum(bool(e['text']) for e in plan['timeline'])<=12
            assert plan['timeline'][-1]['kind']=='result'
            for card in plan['scorecards']:
                assert sum(p['runs'] for p in card['batting'])==sum(p['runs'] for p in card['bowling'])
                assert sum(p['balls'] for p in card['batting'])==sum(p['balls'] for p in card['bowling'])
                assert all(p['balls']<=24 for p in card['bowling'])
                assert sum(p['wickets'] for p in card['bowling'])==sum(p['dismissal'] not in ['not out','did not bat'] for p in card['batting'])
        # Eliminated participants still see the finished bracket and scorecards.
        row.state=state
        assert rooms.project(row,'four',ts+10000)['state']['champion']==state['champion']

def test_concurrent_room_join_cannot_overbook():
    a=client(); b=client('bob'); c=client('charlie')
    room=a.post('/api/rooms',json=dict(name='Host',format='knockout',capacity=2,pick_seconds=10,lobby_minutes=5)).json()
    def join(pair):
        client_,name=pair
        with TestClient(app,headers=dict(client_.headers),cookies=dict(client_.cookies)) as other:
            return other.post('/api/rooms/join',json=dict(code=room['code'],name=name)).status_code
    with ThreadPoolExecutor(max_workers=2) as pool: statuses=list(pool.map(join,[(b,'Bob'),(c,'Charlie')]))
    assert sorted(statuses)==[200,409]
    assert len(a.get(f"/api/rooms/{room['id']}").json()['state']['members'])==2

def test_public_discovery_guest_names_and_self_rename():
    from app.db import Room
    import copy,time
    a=TestClient(app,headers=HEADERS); b=TestClient(app,headers=HEADERS)
    for c in [a,b]: c.headers['x-csrf-token']=c.post('/api/auth/guest',json={}).json()['csrf']
    settings=dict(format='knockout',capacity=2,pick_seconds=30,lobby_minutes=5)
    private=a.post('/api/rooms',json=settings).json()
    public=a.post('/api/rooms',json={**settings,'visibility':'public'}).json()
    assert public['state']['members'][0]['name']=='Player 1'
    listing=b.get('/api/rooms/public').json()
    assert {r['code'] for r in listing['rooms']}=={public['code']}
    assert 'members' not in listing['rooms'][0]
    assert b.get(f"/api/rooms/{public['id']}").status_code==404
    assert b.post(f"/api/rooms/{public['id']}/name",json={'name':'Intruder'}).status_code==404
    joined=b.post('/api/rooms/join',json={'code':public['code']}).json()
    assert [m['name'] for m in joined['state']['members']]==['Player 1','Player 2']
    assert b.post(f"/api/rooms/{public['id']}/name",json={'name':'Player 1'}).status_code==409
    renamed=b.post(f"/api/rooms/{public['id']}/name",json={'name':'Captain Bob'}).json()
    assert renamed['state']['members'][1]['name']=='Captain Bob'
    assert renamed['state']['members'][0]['name']=='Player 1'
    assert b.get('/api/rooms/public').json()['total']==0  # full room disappears
    assert b.post('/api/rooms/join',json={'code':private['code']}).status_code==200
    extra=a.post('/api/rooms',json={**settings,'visibility':'public'}).json()
    with Session.begin() as s:
        row=s.get(Room,extra['id']); state=copy.deepcopy(row.state); state['lobbyDeadline']=time.time()-1; row.state=state
    assert b.get('/api/rooms/public').json()['total']==1  # Legacy deadlines no longer close entry.


def test_user_pagination_block_revoke_and_unblock():
    admin=client('admin'); victim=client('victim'); ordinary=client('ordinary')
    with Session.begin() as s: s.scalar(select(User).where(User.username=='admin')).is_admin=True
    assert ordinary.get('/api/admin/users').status_code==403
    first=admin.get('/api/admin/users?page=1&page_size=2').json()
    second=admin.get('/api/admin/users?page=2&page_size=2').json()
    assert first['total']==3 and len(first['users'])==2 and len(second['users'])==1
    assert not ({u['id'] for u in first['users']} & {u['id'] for u in second['users']})
    assert 'password_hash' not in first['users'][0]
    user_id=victim.get('/api/auth/me').json()['user']['id']
    assert ordinary.post(f'/api/admin/users/{user_id}/admin',json={}).status_code==403
    assert ordinary.post(f'/api/admin/users/{user_id}/status',json={'blocked':True}).status_code==403
    assert admin.post(f'/api/admin/users/{user_id}/status',json={'blocked':True}).status_code==200
    assert admin.post(f'/api/admin/users/{user_id}/admin',json={}).status_code==409
    assert victim.get('/api/games').status_code==401
    assert victim.post('/api/auth/login',json={'email':'victim@example.com','password':'a distinct long passphrase victim'}).status_code==403
    assert admin.post(f'/api/admin/users/{user_id}/status',json={'blocked':False}).status_code==200
    assert victim.post('/api/auth/login',json={'email':'victim@example.com','password':'a distinct long passphrase victim'}).status_code==200
    assert admin.post(f'/api/admin/users/{user_id}/admin',json={'is_admin':True}).status_code==422
    assert admin.post(f'/api/admin/users/{user_id}/admin',json={}).json()=={'id':user_id,'is_admin':True}
    with Session() as s:
        promoted=s.get(User,user_id)
        event=s.scalar(select(Audit).where(Audit.action=='admin.granted',Audit.resource==user_id))
        assert promoted.is_admin is True
        assert event.actor==admin.get('/api/auth/me').json()['user']['id']
        assert event.details=={'source':'dashboard'}
    own=admin.get('/api/auth/me').json()['user']['id']
    assert admin.post(f'/api/admin/users/{own}/status',json={'blocked':True}).status_code==409


def test_email_and_mobile_unique_including_concurrent_registration():
    c=TestClient(app,headers=HEADERS)
    body=dict(username='first',email='first@example.com',phone='8765432109',country_code='+91',password='a suitable long passphrase')
    assert c.post('/api/auth/register',json=body).status_code==201
    assert c.post('/api/auth/register',json={**body,'username':'second','email':'second@example.com'}).status_code==409
    assert c.post('/api/auth/register',json={**body,'username':'third','email':'FIRST@EXAMPLE.COM','phone':'8765432108'}).status_code==409
    # Two different email addresses concurrently claiming the same mobile.
    def register(i):
        with TestClient(app,headers=HEADERS) as other:
            return other.post('/api/auth/register',json={**body,'username':f'racer{i}','email':f'racer{i}@example.com','phone':'8765432107'}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool: statuses=list(pool.map(register,range(2)))
    assert sorted(statuses)==[201,409]

@pytest.mark.parametrize('humans', [1, 2])
def test_partial_room_starts_with_ai_and_completes(humans):
    import time
    import copy
    from app import rooms
    from app.catalog import load_catalog
    from app.db import Room
    host=client(); guest=client('bob'); outsider=client('eve')
    room=host.post('/api/rooms',json=dict(format='knockout',capacity=4,pick_seconds=10,lobby_minutes=5)).json()
    if humans==2:
        room=guest.post('/api/rooms/join',json={'code':room['code']}).json()
        assert guest.post(f"/api/rooms/{room['id']}/actions",json=dict(action='start',version=room['version'])).status_code==403
    room=ready_room(host,room,*([guest] if humans==2 else []))
    response=host.post(f"/api/rooms/{room['id']}/actions",json=dict(action='start',version=room['version']))
    assert response.status_code==200,response.text
    room=response.json(); members=room['state']['members']
    assert len(members)==4 and sum(m['is_ai'] for m in members)==4-humans
    assert len({m['name'].lower() for m in members})==4
    assert all('uid' not in m for m in members)
    late=outsider.post('/api/rooms/join',json={'code':room['code']})
    assert late.status_code==409 and 'Game in progress' in late.json()['detail']
    assert host.post('/api/rooms/join',json={'code':room['code']}).status_code==200
    with Session.begin() as session:
        row=session.get(Room,room['id']); state=copy.deepcopy(row.state)
        players=[p for squad in load_catalog(session)['squads'] for p in squad['players']]
        human_ids=[m['id'] for m in state['members'] if not m['is_ai']]
        assert all(m['uid'] is None for m in state['members'] if m['is_ai'])
        # Clock handles disconnected humans, then gives bots a short independent turn.
        for _ in range(humans): rooms.advance(state,players,state['deadline'])
        assert state['members'][state['turn']]['is_ai']
        before=state['deadline']; rooms.advance(state,players,before)
        assert state['lastPick']['is_ai'] and state['deadline']==before+rooms.AI_PICK_SECONDS
        rooms.advance(state,players,time.time()+10000)
        assert state['phase']=='complete' and state['champion'] and state['award']
        assert len(set(state['taken']))==44
        assert [m['id'] for m in state['members'] if not m['is_ai']]==human_ids
        row.state=state
        visible=rooms.project(row,row.owner_id,time.time()+10000)
        assert all(len(match['scorecards'])==2 for match in visible['state']['matches'])


def test_no_join_deadline_and_live_scorecards_show_only_visible_overs():
    import copy
    import time
    from app import rooms
    from app.catalog import load_catalog
    from app.db import Room
    host=client(); outsider=client('eve')
    room=host.post('/api/rooms',json=dict(format='league',capacity=4,pick_seconds=10,lobby_minutes=5)).json()
    with Session.begin() as session:
        row=session.get(Room,room['id']); state=copy.deepcopy(row.state)
        state['lobbyDeadline']=time.time()-1; row.state=state
    closed=outsider.post('/api/rooms/join',json={'code':room['code']})
    assert closed.status_code==200
    assert 'lobbyDeadline' not in closed.json()['state']
    rooms.tick()
    assert host.get(f"/api/rooms/{room['id']}").json()['state']['phase']=='lobby'
    room=ready_room(host,room,outsider)
    assert host.post(f"/api/rooms/{room['id']}/actions",json=dict(action='start',version=room['version'])).status_code==200
    with Session.begin() as session:
        row=session.get(Room,room['id']); state=copy.deepcopy(row.state)
        assert state['phase']=='draft' and len(state['members'])==4
        assert sum(m['is_ai'] for m in state['members'])==2
        players=[p for squad in load_catalog(session)['squads'] for p in squad['players']]
        while state['phase']=='draft': rooms.advance(state,players,state['deadline'])
        row.state=state
        interval=rooms.playback_seconds(state.get('competition'))
        visible=rooms.project(row,row.owner_id,state['matches'][0]['startedAt']+interval*2)
        for match in visible['state']['matches']:
            assert match['status']=='live' and len(match['timeline'])==2
            assert 'winner' not in match and 'result' not in match
            original=next(m for m in state['matches'] if m['id']==match['id'])
            assert match['scorecards']==original['plan']['timeline'][1]['scorecards']
            assert match['timeline'][0]['text']
            assert all('deliveries' not in e and 'scorecards' not in e for e in match['timeline'])


@pytest.mark.parametrize('phase,message',[('lobby','Room is full'),('draft','Game in progress'),('live','Game in progress'),('complete','tournament has finished'),('expired','room has expired')])
def test_room_entry_status_messages(phase,message):
    import copy
    from app.db import Room
    host=client(); guest=client('bob'); outsider=client('eve')
    room=host.post('/api/rooms',json=dict(format='knockout',capacity=2,pick_seconds=10,lobby_minutes=5)).json()
    assert guest.post('/api/rooms/join',json={'code':room['code']}).status_code==200
    with Session.begin() as session:
        row=session.get(Room,room['id']); state=copy.deepcopy(row.state); state['phase']=phase; row.state=state
    response=outsider.post('/api/rooms/join',json={'code':room['code']})
    assert response.status_code==409 and message in response.json()['detail']
    # Returning members keep their existing seat, including during spectating.
    assert guest.post('/api/rooms/join',json={'code':room['code']}).status_code==200


def room_for(c,capacity=4,kind='knockout'):
    response=c.post('/api/rooms',json=dict(format=kind,capacity=capacity,pick_seconds=30,lobby_minutes=5))
    assert response.status_code==201,response.text
    assert len(response.json()['code'])==4
    return response.json()


def test_practice_no_room_code_preview_order_and_exit():
    from app.db import Room
    c=client(); g=create(c)
    assert g['state']['screen']=='draft' and 'code' not in g
    with Session() as s:
        assert s.get(Game,g['id']).code is None
        assert not s.scalar(select(Room))
    order=[s['id'] for s in SLOTS][::-1]
    assert action(c,g,'formation',order=['op1']*11).status_code==422
    g=action(c,g,'formation',order=order).json()
    for _ in range(11):
        g=action(c,g,'roll').json()
        p,slot=next((p,s) for p in g['state']['rolled']['players'] for s in SLOTS if s['id'] not in g['state']['yourXI'] and p['role'] in s['accepts'])
        g=finish_ai(c,action(c,g,'pick',player_id=p['id'],slot_id=slot['id']).json())
        assert all(p and p['name'] for p in g['state']['opponentXI'].values())
    g=action(c,g,'match').json()
    batting=next(card['batting'] for card in g['state']['match']['scorecards'] if card['side']=='you')
    assert [p['id'] for p in batting]==[g['state']['yourXI'][key]['id'] for key in order]
    assert action(c,g,'formation',order=order).status_code==409
    exited=action(c,g,'exit').json()
    assert exited['state']['abandoned'] and exited['state']['match']['result']['winner']=='opp'
    assert action(c,exited,'roll').status_code==409
    assert action(c,exited,'match').status_code==409


def test_kick_votes_unique_authorized_ai_takeover_and_host_transfer():
    from app.db import Room
    from app import rooms
    a,b,c,d,e=[client(n) for n in ['alice','bob','charlie','dave','eve']]
    room=room_for(a)
    for person in [b,c,d]: room=person.post('/api/rooms/join',json={'code':room['code']}).json()
    room=ready_room(a,room,b,c,d)
    room=a.post(f"/api/rooms/{room['id']}/actions",json=dict(action='start',version=room['version'])).json()
    target=room['you']; url=f"/api/rooms/{room['id']}/kick-vote"
    assert e.post(url,json={'target_id':target}).status_code==404
    assert a.post(url,json={'target_id':target}).status_code==409
    first=b.post(url,json={'target_id':target}); assert first.status_code==200,first.text
    visible=first.json()
    assert visible['state']['kickRequired']==2
    assert next(m for m in visible['state']['members'] if m['id']==target)['kickVotes']==1
    assert 'votes' not in visible['state'] and 'removedUsers' not in visible['state']
    assert b.post(url,json={'target_id':target}).status_code==409
    kicked=c.post(url,json={'target_id':target}); assert kicked.status_code==200,kicked.text
    replacement=next(m for m in kicked.json()['state']['members'] if m['id']==target)
    assert replacement['is_ai'] and replacement['departed'] and len(kicked.json()['state']['members'])==4
    assert a.get(f"/api/rooms/{room['id']}").status_code==403
    assert a.post('/api/rooms/join',json={'code':room['code']}).status_code==403
    assert a.post(f"/api/rooms/{room['id']}/name",json={'name':'Back'}).status_code==403
    assert b.get(f"/api/rooms/{room['id']}").json()['host']
    with Session.begin() as session:
        row=session.get(Room,room['id']); state=__import__('copy').deepcopy(row.state)
        from app.catalog import load_catalog
        players=[p for squad in load_catalog(session)['squads'] for p in squad['players']]
        rooms.advance(state,players,state['deadline'])
        assert state['lastPick']['is_ai'] and len(state['members'][0]['xi'])==1
    with Session() as s: assert s.scalar(select(Audit).where(Audit.action=='room.kicked'))


def test_concurrent_duplicate_kick_vote_counts_once():
    a,b,c,d=[client(n) for n in ['alice','bob','charlie','dave']]
    room=room_for(a)
    for person in [b,c,d]: person.post('/api/rooms/join',json={'code':room['code']})
    def vote(_):
        with TestClient(app,headers=dict(b.headers),cookies=dict(b.cookies)) as other:
            return other.post(f"/api/rooms/{room['id']}/kick-vote",json={'target_id':room['you']}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool: result=list(pool.map(vote,range(2)))
    assert sorted(result)==[200,409]
    state=a.get(f"/api/rooms/{room['id']}").json()['state']
    assert state['members'][0]['kickVotes']==1 and not state['members'][0]['is_ai']


@pytest.mark.parametrize('humans,threshold',[(2,1),(3,2),(4,2),(5,3),(6,3),(7,3),(8,3)])
def test_kick_threshold_excludes_ai(humans,threshold):
    from app import rooms
    state={'members':[rooms.member(str(i),str(i)) for i in range(humans)]+[rooms.member(None,'AI')]*3}
    assert rooms.kick_threshold(state)==threshold


def test_exit_during_draft_preserves_picks_and_formation_permissions():
    from app.db import Room
    a=client(); b=client('bob'); room=room_for(a,2)
    b.post('/api/rooms/join',json={'code':room['code']})
    room=a.get(f"/api/rooms/{room['id']}").json()
    room=ready_room(a,room,b)
    room=a.post(f"/api/rooms/{room['id']}/actions",json=dict(action='start',version=room['version'])).json()
    order=[s['id'] for s in SLOTS][::-1]
    changed=b.post(f"/api/rooms/{room['id']}/actions",json=dict(action='formation',version=room['version'],order=order)).json()
    assert 'order' not in changed['state']['members'][0] and changed['state']['members'][1]['order']==order
    rolled=a.post(f"/api/rooms/{room['id']}/actions",json=dict(action='roll',version=changed['version'])).json()
    player=rolled['state']['rolled']['players'][0]; slot=rolled['state']['rolled']['allowedSlots'][player['id']][0]
    room=a.post(f"/api/rooms/{room['id']}/actions",json=dict(action='pick',version=rolled['version'],player_id=player['id'],slot_id=slot)).json()
    assert a.post(f"/api/rooms/{room['id']}/exit",json={},headers={'x-csrf-token':'bad'}).status_code==403
    assert a.post(f"/api/rooms/{room['id']}/exit",json={}).status_code==200
    visible=b.get(f"/api/rooms/{room['id']}").json()
    assert visible['state']['members'][0]['xi'][slot]['id']==player['id']
    assert visible['state']['members'][0]['is_ai'] and visible['host']
    assert len(visible['state']['taken'])==1
    assert a.post('/api/rooms/join',json={'code':room['code']}).status_code==403


@pytest.mark.parametrize('kind',['knockout','league'])

def test_exit_live_forfeits_without_revealing_future_and_tournament_finishes(kind):
    import copy,time
    from app.db import Room
    from app import rooms
    from app.catalog import load_catalog
    a=client(); b=client('bob'); room=room_for(a,4,kind)
    b.post('/api/rooms/join',json={'code':room['code']})
    with Session.begin() as session:
        row=session.get(Room,room['id']); state=copy.deepcopy(row.state)
        players=[p for squad in load_catalog(session)['squads'] for p in squad['players']]
        for m in state['members']: m['ready']=True
        ts=time.time()-10000; rooms.start(state,ts)
        while state['phase']=='draft': rooms.advance(state,players,state['deadline'])
        for match in state['matches']:
            if match['status']=='live':
                match['startedAt']=time.time()-7; match['endsAt']=time.time()+100
        row.state=state
    departed_id=room['you']
    assert a.post(f"/api/rooms/{room['id']}/exit",json={}).status_code==200
    response=b.get(f"/api/rooms/{room['id']}"); assert response.status_code==200,response.text
    forfeits=[m for m in response.json()['state']['matches'] if m.get('forfeit')]
    assert len(forfeits)==(1 if kind=='knockout' else 3)
    for match in forfeits:
        assert match['winner']!=departed_id and match['status']=='complete'
        assert len(match['timeline'])==2 and 'plan' not in match and match['result']['mvp'] is None
    with Session.begin() as session:
        row=session.get(Room,room['id']); state=copy.deepcopy(row.state)
        rooms.advance(state,players,time.time()+10000)
        assert state['phase']=='complete' and state['champion']!=departed_id
        assert all(m['status']=='complete' for m in state['matches'])
        assert all('plan' not in m for m in state['matches'] if m.get('forfeit'))


def test_short_room_code_collision_retries(monkeypatch):
    from app import room_routes
    a=client(); b=client('bob')
    room=room_for(a,2)
    alternate='YYYY' if room['code']=='ZZZZ' else 'ZZZZ'
    codes=iter(room['code']+alternate)
    monkeypatch.setattr(room_routes.secrets,'choice',lambda _:next(codes))
    other=room_for(b,2)
    assert other['code']==alternate and other['code']!=room['code']


def test_practice_ai_delay_turn_guards_reload_and_exactly_once():
    import copy, time
    from app.game import tick, AI_PICK_SECONDS
    c=client(); g=action(c,create(c),'roll').json()
    p,slot=next((p,s) for p in g['state']['rolled']['players'] for s in SLOTS if p['role'] in s['accepts'])
    before=time.time()
    g=action(c,g,'pick',player_id=p['id'],slot_id=slot['id']).json()
    assert g['state']['turn']=='opp' and g['opponentCount']==0
    assert g['state']['aiDeadline']>=before+AI_PICK_SECONDS
    assert c.get(f"/api/games/{g['id']}").json()['state']['turn']=='opp'
    assert action(c,g,'roll').status_code==409
    assert action(c,g,'pick',player_id=p['id'],slot_id=slot['id']).status_code==409
    assert action(c,g,'match').status_code==409
    deadline=g['state']['aiDeadline']; order=[s['id'] for s in SLOTS][::-1]
    g=action(c,g,'formation',order=order).json()
    assert g['state']['aiDeadline']==deadline
    with Session.begin() as session:
        game=session.get(Game,g['id']); state=copy.deepcopy(game.state)
        state['aiDeadline']=time.time()-1; game.state=state
    tick(); tick()
    after=c.get(f"/api/games/{g['id']}").json()
    assert after['version']==g['version']+1 and after['opponentCount']==1
    assert after['state']['turn']=='you' and after['state']['pickNumber']==3
    assert after['state']['order']==order and 'aiDeadline' not in after['state']
    assert action(c,g,'roll').status_code==409
    with Session() as session:
        assert len(list(session.scalars(select(Audit).where(Audit.action=='game.ai_pick',Audit.resource==g['id']))))==1


def test_exit_cancels_waiting_practice_ai():
    from app.game import advance
    from app.catalog import load_catalog
    c=client(); g=action(c,create(c),'roll').json()
    p,slot=next((p,s) for p in g['state']['rolled']['players'] for s in SLOTS if p['role'] in s['accepts'])
    g=action(c,g,'pick',player_id=p['id'],slot_id=slot['id']).json()
    g=action(c,g,'exit').json()
    with Session() as session:
        assert not advance(g['state'],load_catalog(session)['squads'],g['state']['aiDeadline']+10)
    assert g['opponentCount']==0


def test_room_roll_scope_turn_permissions_rerolls_and_timeout():
    import copy, time
    from app.db import Room
    from app.catalog import load_catalog
    from app import rooms
    a=client(); b=client('bob'); outsider=client('eve'); r=room_for(a,2)
    r=b.post('/api/rooms/join',json={'code':r['code']}).json()
    url=f"/api/rooms/{r['id']}/actions"
    r=ready_room(a,r,b)
    r=a.post(url,json=dict(action='start',version=r['version'])).json()
    deadline=r['state']['deadline']
    assert a.post(url,json=dict(action='pick',version=r['version'],player_id='0-0',slot_id='op1')).status_code==409
    assert b.post(url,json=dict(action='roll',version=r['version'])).status_code==403
    assert outsider.post(url,json=dict(action='roll',version=r['version'])).status_code==404
    old=r
    r=a.post(url,json=dict(action='roll',version=r['version'])).json()
    assert a.post(url,json=dict(action='roll',version=old['version'])).status_code==409
    rolled=r['state']['rolled']; ids={p['id'] for p in rolled['players']}
    assert 0<len(ids)<20 and len({p['squad'] for p in rolled['players']})==1
    assert r['state']['deadline']>deadline and r['state']['members'][0]['rerollsUsed']==0
    assert r['state']['deadline']==r['serverTime']+r['state']['seconds']
    deadline=r['state']['deadline']
    assert b.get(f"/api/rooms/{r['id']}").json()['state']['rolled'] is None
    assert a.get(f"/api/rooms/{r['id']}").json()['state']['rolled']==rolled
    with Session() as session:
        players=[p for squad in load_catalog(session)['squads'] for p in squad['players']]
        outside=next(o for o in rooms.eligible(session.get(Room,r['id']).state,players) if o['player']['id'] not in ids)
    assert a.post(url,json=dict(action='pick',version=r['version'],player_id=outside['player']['id'],slot_id=outside['slot'])).status_code==409
    for used in range(1,4):
        r=a.post(url,json=dict(action='roll',version=r['version'])).json()
        assert r['state']['members'][0]['rerollsUsed']==used
        assert r['state']['deadline']==r['serverTime']+r['state']['seconds']
        assert r['state']['deadline']>deadline
        # The original timeout must not fire after a successful reroll.
        with Session() as session:
            snapshot=copy.deepcopy(session.get(Room,r['id']).state)
        assert not rooms.advance(snapshot,players,(deadline+r['state']['deadline'])/2)
        deadline=r['state']['deadline']
    assert a.post(url,json=dict(action='roll',version=r['version'])).status_code==409
    assert a.get(f"/api/rooms/{r['id']}").json()['state']['deadline']==deadline
    last_ids={p['id'] for p in r['state']['rolled']['players']}
    # A timer expiry must select from the already rolled squad.
    with Session.begin() as session:
        row=session.get(Room,r['id']); state=copy.deepcopy(row.state); state['deadline']=time.time()-1; row.state=state
    rooms.tick()
    r=b.get(f"/api/rooms/{r['id']}").json()
    assert r['state']['turn']==1 and r['state']['rolled'] is None
    assert r['state']['taken'][0] in last_ids and r['state']['lastPick']['automatic']
    r=b.post(url,json=dict(action='roll',version=r['version'])).json()
    assert r['state']['members'][1]['rerollsUsed']==0
    assert not set(r['state']['taken']) & set(r['state']['rolled']['allowedSlots'])
    player=next(p for p in r['state']['rolled']['players'] if p['id'] in r['state']['rolled']['allowedSlots']); slot=r['state']['rolled']['allowedSlots'][player['id']][0]
    r=b.post(url,json=dict(action='pick',version=r['version'],player_id=player['id'],slot_id=slot)).json()
    assert r['state']['turn']==0 and r['state']['rolled'] is None
    # Each fresh turn has a free initial roll, even after three rerolls were spent.
    response=a.post(url,json=dict(action='roll',version=r['version']))
    assert response.status_code==200,response.text
    assert response.json()['state']['members'][0]['rerollsUsed']==3


def test_room_concurrent_roll_once_and_invalid_position_rejected():
    c=client(); r=room_for(c,2); url=f"/api/rooms/{r['id']}/actions"
    r=ready_room(c,r)
    r=c.post(url,json=dict(action='start',version=r['version'])).json()
    def roll(_):
        with TestClient(app,headers=dict(c.headers),cookies=dict(c.cookies)) as other:
            return other.post(url,json=dict(action='roll',version=r['version'])).status_code
    with ThreadPoolExecutor(max_workers=2) as pool: statuses=list(pool.map(roll,range(2)))
    assert sorted(statuses)==[200,409]
    visible=c.get(f"/api/rooms/{r['id']}").json()
    assert visible['version']==r['version']+1 and visible['state']['members'][0]['rerollsUsed']==0
    player=visible['state']['rolled']['players'][0]
    forbidden=next(s['id'] for s in SLOTS if s['id'] not in visible['state']['rolled']['allowedSlots'][player['id']])
    assert c.post(url,json=dict(action='pick',version=visible['version'],player_id=player['id'],slot_id=forbidden)).status_code==409
    assert c.post(url,json=dict(action='roll',version=visible['version'],squad='INDIA')).status_code==422


def test_full_room_squad_visible_but_taken_players_cannot_be_picked(monkeypatch):
    from fastapi import HTTPException
    from app import rooms
    from app.catalog import load_catalog
    from app.db import Room
    a=client(); b=client('bob'); r=room_for(a,2)
    r=b.post('/api/rooms/join',json={'code':r['code']}).json()
    url=f"/api/rooms/{r['id']}/actions"
    r=ready_room(a,r,b)
    r=a.post(url,json=dict(action='start',version=r['version'])).json()
    monkeypatch.setattr(rooms.rng,'choice',lambda choices:next(x for x in choices if x=='INDIA 2011'))
    r=a.post(url,json=dict(action='roll',version=r['version'])).json()
    full_ids={p['id'] for p in r['state']['rolled']['players']}
    r=a.post(url,json=dict(action='pick',version=r['version'],player_id='0-0',slot_id='op1')).json()
    r=b.post(url,json=dict(action='roll',version=r['version'])).json()
    assert {p['id'] for p in r['state']['rolled']['players']}==full_ids
    assert '0-0' in r['state']['taken'] and '0-0' not in r['state']['rolled']['allowedSlots']
    assert b.post(url,json=dict(action='pick',version=r['version'],player_id='0-0',slot_id='op1')).status_code==409
    def pick(_):
        with TestClient(app,headers=dict(b.headers),cookies=dict(b.cookies)) as other:
            return other.post(url,json=dict(action='pick',version=r['version'],player_id='0-1',slot_id='op1')).status_code
    with ThreadPoolExecutor(max_workers=2) as pool: statuses=list(pool.map(pick,range(2)))
    assert sorted(statuses)==[200,409]
    visible=a.get(f"/api/rooms/{r['id']}").json()
    assert set(visible['state']['taken'])=={'0-0','0-1'} and len(visible['state']['taken'])==2
    # A full position also disables an untaken player, without hiding them.
    with Session() as session:
        players=[p for squad in load_catalog(session)['squads'] for p in squad['players']]
        state=session.get(Room,r['id']).state
        keeper=next(p for p in players if p['id']=='1-0')
        state['members'][0]['xi']['wk']=keeper; state['taken'].append(keeper['id'])
        rooms.roll(state,players)
        assert '0-6' in {p['id'] for p in state['rolled']['players']}
        assert '0-6' not in state['rolled']['allowedSlots']
        with pytest.raises(HTTPException) as exc:
            rooms.pick(state,players,0,'0-6','wk')
        assert exc.value.status_code==409


@pytest.mark.parametrize('phase',['draft','live','complete'])

def test_room_name_locks_after_selection_starts(phase):
    import copy
    from app.db import Room
    c=client(); room=room_for(c,2)
    with Session.begin() as session:
        row=session.get(Room,room['id']); state=copy.deepcopy(row.state)
        state['phase']=phase; row.state=state
    response=c.post(f"/api/rooms/{room['id']}/name",json={'name':'Changed winner'})
    assert response.status_code==409
    with Session() as session:
        assert session.get(Room,room['id']).state['members'][0]['name']=='alice'
