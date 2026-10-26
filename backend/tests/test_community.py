import copy
import time
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.main import app
from app.db import Session, Room, User, Game, MatchArchive, MatchPlayer, Achievement, Cup
from app import rooms, game
from app.catalog import load_catalog, SLOTS
from app.draft_pool import person_key
from app.progression import cup_standings, engagement
from app.presets import validate_pool
from test_preflight import clean, client, HEADERS, ready_room

def group_for(*clients):
    response=clients[0].post('/api/groups',json={'name':'The Pavilion'})
    assert response.status_code==201,response.text
    group=clients[0].get('/api/groups/'+response.json()['id']).json()
    for c in clients[1:]:
        r=c.post('/api/groups/join',json={'invite':group['invite']}); assert r.status_code==200,r.text
    return clients[0].get('/api/groups/'+group['id']).json()

def start_cup(a,group,preset='under-85'):
    response=a.post(f"/api/groups/{group['id']}/cups",json={'preset':preset})
    assert response.status_code==201,response.text
    return a.get('/api/groups/'+group['id']).json()['cups'][0]

def fixture_room(a,b,group,fixture):
    response=a.post(f"/api/groups/{group['id']}/fixtures/{fixture['id']}",json={})
    assert response.status_code==200,response.text
    room=a.post('/api/rooms/join',json=response.json()).json()
    assert b.post('/api/rooms/join',json={'code':room['code']}).status_code==200
    return room

def complete_room(room_id,winner_id=None):
    # Advance an isolated test match, using real pool, simulation and settlement.
    with Session.begin() as session:
        room=session.get(Room,room_id); state=copy.deepcopy(room.state)
        for m in state['members']: m['ready']=True
        rooms.start(state,time.time()-10000)
        players=[p for squad in load_catalog(session,state['competition'])['squads'] for p in squad['players']]
        while state['phase']=='draft': rooms.advance(state,players,state['deadline'])
        if winner_id:
            winner=next(m for m in state['members'] if m['uid']==winner_id)
            match=state['matches'][0]; match['winner']=winner['id']; match['plan']['result']['winner']='you' if match['a']==winner['id'] else 'opp'
        room.state=state
    rooms.tick()

def guest():
    c=TestClient(app,headers=HEADERS); response=c.post('/api/auth/guest',json={}); c.headers['x-csrf-token']=response.json()['csrf']; return c

def seed_practice(c,preset='under-85'):
    response=c.post('/api/games',json={'preset':preset}); assert response.status_code==201,response.text
    saved=response.json()
    with Session.begin() as session:
        row=session.get(Game,saved['id']); state=copy.deepcopy(row.state)
        squads=load_catalog(session,'ipl')['squads']
        for _ in range(11):
            game.act(state,'roll',squads=squads)
            p,s=next((p,s) for p in state['rolled']['players'] for s in SLOTS if s['id'] not in state['yourXI'] and p['role'] in s['accepts'] and game.fits(state,p))
            game.act(state,'pick',p['id'],s['id'],squads=squads)
            while state['turn']=='opp': game.advance(state,squads,state['aiDeadline'])
        game.act(state,'match',squads=[]); row.state=state
    return saved['id']

def test_achievements_are_locked_until_completion_private_and_share_only_on_request():
    a=client(); b=client('bob')
    assert all(not item['earnedAt'] for item in a.get('/api/progress').json()['achievements'])
    assert a.post('/api/achievements/first-xi/share',json={}).status_code==409
    gid=seed_practice(a)
    assert not a.get('/api/progress').json()['history']  # Simulation alone is not a viewed result.
    assert b.post(f'/api/games/{gid}/complete',json={}).status_code==404
    for _ in range(2): assert a.post(f'/api/games/{gid}/complete',json={}).status_code==200
    progress=a.get('/api/progress').json()
    earned={x['code'] for x in progress['achievements'] if x['earnedAt']}
    assert earned=={'first-xi','under-85'}  # AI never awards a rival win.
    assert len(progress['history'])==1
    assert not b.get('/api/progress').json()['history']
    share=a.post('/api/achievements/under-85/share',json={}).json()['path']
    card=TestClient(app).get('/api/shares/achievements/'+share.split('/')[-1])
    assert card.status_code==200 and card.json()['title']=='Hidden gems'
    assert set(card.json())=={'code','title','description','target','metric','variant','name','earnedAt'}
    assert 'email' not in card.text and 'userId' not in card.text
    assert b.post('/api/achievements/under-85/share',json={}).status_code==409

def test_guest_registration_claims_trophies_without_phone_and_preserves_share():
    c=guest(); gid=seed_practice(c); c.post(f'/api/games/{gid}/complete',json={})
    share=c.post('/api/achievements/first-xi/share',json={}).json()['path']
    registered=c.post('/api/auth/register',json={'username':'savedplayer','email':'saved@example.com','password':'a strong cricket passphrase'})
    assert registered.status_code==201,registered.text
    c.headers['x-csrf-token']=registered.json()['csrf']
    assert len(c.get('/api/progress').json()['history'])==1
    assert not c.get('/api/progress').json()['guest']
    assert TestClient(app).get('/api/shares/achievements/'+share.split('/')[-1]).json()['name']=='savedplayer'
    assert c.get(f'/api/games/{gid}').status_code==200

def test_signin_claims_guest_history_and_earned_trophies():
    client('alice'); c=guest(); gid=seed_practice(c); c.post(f'/api/games/{gid}/complete',json={})
    response=c.post('/api/auth/login',json={'email':'alice@example.com','password':'a distinct long passphrase alice'})
    assert response.status_code==200,response.text
    c.headers['x-csrf-token']=response.json()['csrf']
    assert c.get('/api/progress').json()['stats']['completed']==1
    assert c.get(f'/api/games/{gid}').status_code==200

def test_recovery_codes_are_one_use_revoke_sessions_and_preserve_progress():
    a=client(); other=TestClient(app,headers=HEADERS)
    code=a.post('/api/auth/recovery-code',json={}).json()['code']
    with Session() as session:
        from app.db import AccountRecovery
        assert session.scalar(select(AccountRecovery)).token_hash!=code
    payload=dict(email='alice@example.com',code=code,password='a different long passphrase')
    assert other.post('/api/auth/recover',json={**payload,'code':'invalid-recovery-code'}).status_code==401
    assert other.post('/api/auth/recover',json=payload).status_code==200
    assert a.get('/api/auth/me').status_code==401
    assert other.post('/api/auth/recover',json=payload).status_code==401
    assert other.post('/api/auth/login',json=dict(email=payload['email'],password=payload['password'])).status_code==200

def test_cup_example_unequal_friendly_volume_does_not_change_fixed_fixture_points():
    state=dict(roster=[dict(id=name,name=name) for name in ['Asha','Bharat','Chitra','Dev']],fixtures=[])
    for a,b,winner in [('Asha','Bharat','Asha'),('Asha','Chitra','Chitra'),('Asha','Dev','Asha'),('Bharat','Chitra','Chitra'),('Bharat','Dev','Bharat'),('Chitra','Dev','Chitra')]:
        state['fixtures'].append(dict(a=a,b=b,winner=winner,status='complete'))
    assert [(r['name'],r['played'],r['points']) for r in cup_standings(state)]==[('Chitra',3,6),('Asha',3,4),('Bharat',3,2),('Dev',3,0)]

def test_engagement_distinguishes_simulation_from_viewed_result_and_survives_game_deletion():
    from datetime import timedelta
    from app.db import now
    c=client(); gid=seed_practice(c)
    with Session() as session: assert engagement(session,now()-timedelta(days=30))['completedMatches']==0
    c.post(f'/api/games/{gid}/complete',json={})
    with Session.begin() as session: session.delete(session.get(Game,gid))
    with Session() as session:
        data=engagement(session,now()-timedelta(days=30))
        assert data['completedMatches']==data['practiceResultsViewed']==1
        assert data['returningPlayers']==data['rematchesCompleted']==0

def test_concurrent_practice_completions_do_not_deadlock_or_duplicate_unlocks():
    from concurrent.futures import ThreadPoolExecutor
    c=client(); first=seed_practice(c)
    with Session.begin() as session:
        original=session.get(Game,first)
        second=Game(owner_id=original.owner_id,state=copy.deepcopy(original.state)); session.add(second); session.flush(); second_id=second.id
    def complete(gid):
        other=TestClient(app,headers=dict(c.headers),cookies=dict(c.cookies))
        return other.post(f'/api/games/{gid}/complete',json={}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(complete,[first,second_id]))
    assert results==[200,200]
    assert c.get('/api/progress').json()['stats']['completed']==2
    with Session() as session: assert session.scalar(select(func.count()).select_from(Achievement).where(Achievement.code=='first-xi'))==1

def test_group_access_roster_freezing_and_invitation_rotation():
    a,b,c=client(),client('bob'),client('charlie'); group=group_for(a,b)
    assert guest().post('/api/groups',json={'name':'Transient'}).status_code==403
    assert c.get('/api/groups/'+group['id']).status_code==404
    assert b.post(f"/api/groups/{group['id']}/cups",json={}).status_code==403
    cup=start_cup(a,group)
    assert len(cup['roster'])==2 and len(cup['fixtures'])==3
    assert a.post(f"/api/groups/{group['id']}/cups",json={}).status_code==409
    assert c.post('/api/groups/join',json={'invite':group['invite']}).status_code==200
    frozen=a.get('/api/groups/'+group['id']).json()['cups'][0]
    assert frozen['roster']==cup['roster']
    assert c.post(f"/api/groups/{group['id']}/fixtures/{cup['fixtures'][0]['id']}",json={}).status_code==403
    assert b.post(f"/api/groups/{group['id']}/invite",json={}).status_code==403
    assert a.post(f"/api/groups/{group['id']}/invite",json={}).status_code==200
    assert c.post('/api/groups/join',json={'invite':group['invite']}).status_code==404

def test_best_of_three_closes_after_two_wins_no_double_points_and_survives_room_cleanup():
    a,b=client(),client('bob'); group=group_for(a,b); cup=start_cup(a,group); winner=a.get('/api/auth/me').json()['user']['id']
    assert a.post(f"/api/groups/{group['id']}/fixtures/{cup['fixtures'][1]['id']}",json={}).status_code==409
    for fixture in cup['fixtures'][:2]:
        room=fixture_room(a,b,group,fixture); complete_room(room['id'],winner)
        for c in [a,b]:
            assert c.get('/api/rooms/'+room['id']).status_code==200
            assert c.post('/api/rooms/'+room['id']+'/exit',json={}).status_code==200
    detail=a.get('/api/groups/'+group['id']).json(); final=detail['cups'][0]
    assert final['status']=='complete' and final['winners']==[winner]
    assert final['fixtures'][2]['status']=='not-needed'
    assert final['standings'][0]['points']==4
    assert len(detail['history'])==2 and detail['rivalries'][0]['played']==2
    earned={x['code'] for x in a.get('/api/progress').json()['achievements'] if x['earnedAt']}
    assert {'first-xi','first-rival-win','rivalry','under-85','cup-finisher','cup-champion'}<=earned
    with Session() as session: assert session.scalar(select(func.count()).select_from(Room))==0

def test_cup_requires_scheduled_humans_no_kicking_and_draft_withdrawal_is_forfeit():
    a,b,c=client(),client('bob'),client('charlie'); group=group_for(a,b); cup=start_cup(a,group)
    invitation=a.post(f"/api/groups/{group['id']}/fixtures/{cup['fixtures'][0]['id']}",json={}).json()
    room=a.post('/api/rooms/join',json=invitation).json(); path='/api/rooms/'+room['id']
    assert c.post('/api/rooms/join',json=invitation).status_code==403
    room=a.post(path+'/ready',json={'ready':True}).json()
    assert a.post(path+'/actions',json={'action':'start','version':room['version']}).status_code==409
    b.post('/api/rooms/join',json=invitation); room=ready_room(a,room,b)
    target=next(m for m in room['state']['members'] if m['id']!=room['you'])['id']
    assert a.post(path+'/kick-vote',json={'target_id':target}).status_code==409
    room=a.post(path+'/actions',json={'action':'start','version':room['version']}).json()
    assert room['state']['phase']=='draft'
    assert a.post(path+'/exit',json={}).status_code==200
    detail=b.get('/api/groups/'+group['id']).json()
    assert detail['cups'][0]['fixtures'][0]['forfeit']
    assert detail['cups'][0]['standings'][0]['points']==2
    assert not any(x['earnedAt'] for x in b.get('/api/progress').json()['achievements'])

def test_lobby_exit_releases_fixture_without_points():
    a,b=client(),client('bob'); group=group_for(a,b); cup=start_cup(a,group)
    room=fixture_room(a,b,group,cup['fixtures'][0])
    assert a.post('/api/rooms/'+room['id']+'/exit',json={}).status_code==200
    detail=b.get('/api/groups/'+group['id']).json()['cups'][0]
    assert detail['fixtures'][0]['status']=='pending'
    assert all(r['points']==0 for r in detail['standings'])
    assert fixture_room(b,a,group,detail['fixtures'][0])['id']!=room['id']

def test_archiving_cup_cancels_unstarted_lobbies_and_started_fixtures_block_archive():
    a,b=client(),client('bob'); group=group_for(a,b); cup=start_cup(a,group)
    room=fixture_room(a,b,group,cup['fixtures'][0]); room=ready_room(a,room,b)
    path=f"/api/groups/{group['id']}/cups/{cup['id']}/archive"
    assert a.post(path,json={}).status_code==200
    assert a.post('/api/rooms/'+room['id']+'/actions',json={'action':'start','version':room['version']}).status_code==409
    assert a.get('/api/groups/'+group['id']).json()['cups'][0]['status']=='unfinished'
    next_cup=start_cup(a,group); room=fixture_room(a,b,group,next_cup['fixtures'][0]); room=ready_room(a,room,b)
    assert a.post('/api/rooms/'+room['id']+'/actions',json={'action':'start','version':room['version']}).status_code==200
    assert a.post(f"/api/groups/{group['id']}/cups/{next_cup['id']}/archive",json={}).status_code==409

def test_tied_round_robin_shares_title_and_friendlies_cannot_add_points():
    clients=[client('alice'),client('bob'),client('charlie')]; group=group_for(*clients); cup=start_cup(clients[0],group,'open-ipl')
    identities=[c.get('/api/auth/me').json()['user']['id'] for c in clients]; by_id=dict(zip(identities,clients))
    wins={identities[0]:identities[1],identities[1]:identities[2],identities[2]:identities[0]}
    for f in cup['fixtures']:
        a,b=by_id[f['a']],by_id[f['b']]; room=fixture_room(a,b,group,f)
        winner=f['a'] if wins[f['a']]==f['b'] else f['b']; complete_room(room['id'],winner)
    final=clients[0].get('/api/groups/'+group['id']).json()['cups'][0]
    assert set(final['winners'])==set(identities)
    assert all(r['points']==2 and r['rank']==1 for r in final['standings'])
    code=clients[0].post(f"/api/groups/{group['id']}/friendly",json={'preset':'open-ipl'}).json()
    room=clients[0].post('/api/rooms/join',json=code).json(); clients[1].post('/api/rooms/join',json=code)
    complete_room(room['id'],identities[0])
    assert clients[0].get('/api/groups/'+group['id']).json()['cups'][0]['standings']==final['standings']

def test_rematch_invitation_is_shared_preserves_group_and_is_a_friendly():
    a,b=client(),client('bob'); group=group_for(a,b); cup=start_cup(a,group); room=fixture_room(a,b,group,cup['fixtures'][0]); complete_room(room['id'])
    one=a.post('/api/rooms/'+room['id']+'/rematch',json={}); two=b.post('/api/rooms/'+room['id']+'/rematch',json={})
    assert one.status_code==two.status_code==200 and one.json()==two.json()
    next_room=b.post('/api/rooms/join',json=two.json()).json()
    assert next_room['state']['groupId']==group['id'] and not next_room['state']['cupId']
    assert next_room['state']['preset']=='under-85'
    assert a.get('/api/rooms/'+room['id']).json()['state']['rematchCode']==one.json()['code']

def test_public_rematch_preserves_visibility_and_guest_display_name():
    c=guest()
    room=c.post('/api/rooms',json=dict(format='knockout',capacity=2,pick_seconds=30,competition='t20',visibility='public')).json()
    c.post('/api/rooms/'+room['id']+'/name',json={'name':'Guest Rival'})
    complete_room(room['id'])
    invitation=c.post('/api/rooms/'+room['id']+'/rematch',json={})
    assert invitation.status_code==200,invitation.text
    next_room=c.post('/api/rooms/join',json=invitation.json()).json()
    assert next_room['visibility']=='public'
    assert next_room['state']['members'][0]['name']=='Guest Rival'

@pytest.mark.parametrize('preset',['open-ipl','under-85'])
def test_presets_can_fill_eight_unique_xis_and_filter_both_practice_teams(preset,monkeypatch):
    with Session() as session:
        validate_pool(session,preset,8)
        squads=load_catalog(session,'ipl')['squads']; players=[p for s in squads for p in s['players']]
    state=rooms.new_state('host',SimpleNamespace(name='Host',capacity=8,format='knockout',pick_seconds=30,competition='ipl'))
    state['preset']=preset; state['members'][0]['ready']=True; rooms.start(state,1)
    monkeypatch.setattr(rooms,'fixtures',lambda *_:None)
    while state['phase']=='draft': rooms.pick(state,players,1,automatic=True)
    selected=[p for m in state['members'] for p in m['xi'].values()]
    assert len({person_key(p) for p in selected})==88
    assert all(p['competition']=='ipl' and (preset!='under-85' or p['rating']<85) for p in selected)
    c=client(); gid=seed_practice(c,preset)
    saved=c.get('/api/games/'+gid).json()['state']
    assert all(p['competition']=='ipl' and (preset!='under-85' or p['rating']<85) for xi in ['yourXI','opponentXI'] for p in saved[xi].values())
