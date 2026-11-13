import copy
import json
from pathlib import Path
from uuid import uuid4
from app import game, match_review
from app.db import Session,Room
from test_preflight import clean,client,room_for,ready_room
from test_realtime import ticket,authenticate


def test_ready_name_lock_and_host_settings_reset_readiness():
    a,b=client(),client('bob'); room=room_for(a,2); path='/api/rooms/'+room['id']
    b.post('/api/rooms/join',json={'code':room['code']}); room=ready_room(a,room,b)
    assert a.post(path+'/name',json={'name':'New Name'}).status_code==409
    settings=dict(version=room['version'],format='league',capacity=2,pick_seconds=60,competition='ipl',visibility='private')
    assert b.post(path+'/settings',json=settings).status_code==403
    response=a.post(path+'/settings',json=settings);assert response.status_code==200,response.text
    room=response.json();assert room['state']['seconds']==60 and not any(m['ready'] for m in room['state']['members'])
    assert a.post(path+'/name',json={'name':'New Name'}).status_code==200
    assert a.post(path+'/settings',json=settings).status_code==409
    room=ready_room(a,a.get(path).json(),b)
    a.post(path+'/actions',json={'action':'start','version':room['version']})
    settings['version']=a.get(path).json()['version']
    assert a.post(path+'/settings',json=settings).status_code==409


def test_chat_membership_csrf_dedup_and_websocket_delivery():
    a,b,eve=client(),client('bob'),client('eve');room=room_for(a,2);path='/api/rooms/'+room['id']
    b.post('/api/rooms/join',json={'code':room['code']})
    message=dict(text='<script>alert(1)</script>',nonce=str(uuid4()))
    assert eve.post(path+'/chat',json=message).status_code==404
    assert a.post(path+'/chat',json=message,headers={'x-csrf-token':'wrong'}).status_code==403
    assert a.post(path+'/chat',json={**message,'text':'  '}).status_code==422
    assert a.post(path+'/chat',json={**message,'text':'x'*301}).status_code==422
    with b, b.websocket_connect(path+'/live') as socket:
        authenticate(socket,ticket(b,room))
        assert a.post(path+'/chat',json=message).status_code==200
        assert a.post(path+'/chat',json=message).status_code==200
        for _ in range(5):
            event=socket.receive_json()
            if event.get('room',{}).get('state',{}).get('chat'):break
        messages=event['room']['state']['chat']
        assert len(messages)==1 and messages[0]['text']==message['text']
    assert b.get(path).json()['state']['chat']==messages


def test_chat_is_bounded_and_does_not_invalidate_draft_revision():
    a=client();room=ready_room(a,room_for(a,2));path='/api/rooms/'+room['id']
    room=a.post(path+'/actions',json={'action':'start','version':room['version']}).json();revision=room['state']['draftRevision']
    with Session.begin() as s:
        row=s.get(Room,room['id']);state=copy.deepcopy(row.state)
        state['chat']=[dict(id=str(uuid4()),sender=room['you'],name='A',text='Old',sentAt=i) for i in range(60)];row.state=state
    a.post(path+'/chat',json=dict(text='Newest',nonce=str(uuid4())))
    after=a.get(path).json()
    assert len(after['state']['chat'])==60 and after['state']['chat'][-1]['text']=='Newest'
    response=a.post(path+'/actions',json=dict(action='roll',version=room['version'],draft_revision=revision))
    assert response.status_code==200
    rolled=response.json();state=rolled['state'];actor=state['members'][state['turn']]
    assert actor['lastRoll']=={key:state['rolled'][key] for key in ('country','tournament')}
    assert set(actor['lastRoll'])=={'country','tournament'}
    player_id,slots=next(iter(state['rolled']['allowedSlots'].items()))
    picked=a.post(path+'/actions',json=dict(action='pick',version=rolled['version'],draft_revision=state['draftRevision'],player_id=player_id,slot_id=slots[0]))
    assert picked.status_code==200,picked.text
    saved=next(m for m in picked.json()['state']['members'] if m['id']==actor['id'])
    assert saved['lastRoll']==actor['lastRoll']
    assert saved['lastSelected']==next(p['name'] for p in state['rolled']['players'] if p['id']==player_id)


def test_reviews_match_scorecards_and_venue_applies_to_ipl():
    data=json.loads(Path('app/catalog.json').read_text())
    teams=[]
    for prefix in ('a','b'):
        teams.append({s['id']:dict(id=prefix+str(i),name=prefix+str(i),role=s['accepts'][0],rating=85,squad='TEST 2024',competition='ipl') for i,s in enumerate(data['slots'])})
    plan=game.simulate(*teams)
    assert plan['result']['winner'] in ('you','opp')
    analysis=plan['result']['analysis']
    assert plan['venue']['id'] in {v['id'] for v in match_review.VENUES}
    for card in plan['scorecards']:
        metric=analysis['metrics'][card['side']]
        assert metric['runs']==sum(p['runs'] for p in card['batting'])
        assert metric['boundaryRuns']==sum(4*p['fours']+6*p['sixes'] for p in card['batting'])
    assert len(analysis['teams'])==2 and all(len(t['players'])==11 for t in analysis['teams'])
    assert match_review.skills(dict(role='PACE',rating=99))['batting']<match_review.skills(dict(role='BAT',rating=90))['batting']


def test_rating_evidence_matches_cards_and_seasons():
    evidence=json.loads(Path('app/rating-evidence.json').read_text());cards={p['id']:p for s in json.loads(Path('app/catalog.json').read_text())['squads'] for p in s['players']}
    assert len(evidence)==53
    for id,item in evidence.items():
        assert cards[id]['rating']==item['rating'] and cards[id]['squad']==item['squad']
        assert item['source'].startswith('https://')
    assert cards['332-22']['rating']<cards['389-17']['rating']


def test_nonhost_rematch_keeps_host_code_and_both_rounds_history():
    from test_community import complete_room
    from app.db import MatchArchive
    from sqlalchemy import select
    a,b=client(),client('bob');room=room_for(a,2);path='/api/rooms/'+room['id']
    b.post('/api/rooms/join',json={'code':room['code']})
    complete_room(room['id'])
    first=a.get(path).json();first_ids={m['id'] for m in first['state']['matches']}
    result=b.post(path+'/rematch',json={});assert result.status_code==200,result.text
    assert result.json()['code']==room['code']
    same=a.get(path).json();assert same['host'] and same['state']['phase']=='lobby'
    assert not b.get(path).json()['host']
    assert a.post(path+'/rematch',json={}).json()==result.json()
    complete_room(room['id'])
    second=a.get(path).json();assert not first_ids.intersection(m['id'] for m in second['state']['matches'])
    with Session() as session:
        records=list(session.scalars(select(MatchArchive).where(MatchArchive.id.like('room:'+room['id']+':%'))))
        assert len(records)==2 and sum(bool(r.data['rematch']) for r in records)==1


def test_review_counts_runouts_without_crediting_bowlers():
    slots=json.loads(Path('app/catalog.json').read_text())['slots']
    teams={side:{s['id']:dict(name=s['id'],role=s['accepts'][0],rating=85) for s in slots} for side in ('you','opp')}
    def card(side,runs,wickets,bowling_wickets):
        return dict(side=side,score=f'{runs}/{wickets} (20.0)',
                    batting=[dict(name=side,runs=runs,balls=120,fours=0,sixes=0)],
                    bowling=[dict(name='Bowler',runs=runs,balls=120,wickets=bowling_wickets)])
    cards=[card('you',106,0,0),card('opp',100,9,8)]
    plan=dict(scorecards=cards,result=dict(winner='you',margin='by 6 runs'),firstBatting='you',overs=20,
              timeline=[dict(over='OV 20',batting='opp',scorecards=cards)])
    analysis=match_review.review(plan,teams,dict(you='A',opp='B'),match_review.VENUES[0],external=True)['result']['analysis']
    assert analysis['metrics']['you']['wicketsTaken']==9
    assert any('9 wickets (8 credited to bowlers)' in n for n in analysis['teams'][0]['details'])
    assert 'needing 7 more runs to win' in analysis['teams'][1]['summary']
    assert not any(n.startswith('Overs ') for n in analysis['teams'][1]['details'])
    assert 'between' not in analysis['decisive']  # Sparse snapshots cannot prove a short spell.
