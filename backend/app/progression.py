"""Server-earned milestones and independent, idempotent match records."""
import copy
from collections import Counter
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from .db import Achievement, Audit, Cup, MatchArchive, MatchPlayer, User, now
from .draft_pool import person_key

ACHIEVEMENTS = [
    dict(code='first-xi', title='First XI', description='Complete a match with eleven drafted players. Forfeits do not count.', target=1, metric='completed', variant='player'),
    dict(code='first-rival-win', title='Bragging rights', description='Win a completed match against another human. AI wins and forfeits do not count.', target=1, metric='humanWins', variant='cup'),
    dict(code='rivalry', title='Run it back', description='Complete two matches against the same human rival. Forfeits do not count.', target=2, metric='rivalMatches', variant='player'),
    dict(code='explorer', title='Archive explorer', description='Use 25 different cricketers in completed matches. Editions of the same player count once.', target=25, metric='players', variant='player'),
    dict(code='under-85', title='Hidden gems', description='Complete an IPL Under 85 match with a full XI. Winning is optional.', target=1, metric='under85', variant='player'),
    dict(code='cup-finisher', title='See it through', description='Finish every required fixture in a completed friend cup without withdrawing.', target=1, metric='cupsFinished', variant='cup'),
    dict(code='cup-champion', title='Your circle, your crown', description='Win a completed friend cup, including a shared title. Friendly matches never award cup points.', target=1, metric='cupsWon', variant='cup'),
]

def unlock(session, user_id, code, source):
    stmt = insert(Achievement).values(user_id=user_id, code=code, source=source, earned_at=now()).on_conflict_do_nothing(index_elements=['user_id', 'code']).returning(Achievement.code)
    if session.scalar(stmt): session.add(Audit(action='achievement.earned', actor=user_id, resource=source[:36], details={'code':code}))

def stats(session, user_id):
    records = session.scalars(select(MatchArchive).join(MatchPlayer).where(MatchPlayer.user_id==user_id)).all()
    completed=human_wins=under85=0; rivals=Counter(); people=set()
    for record in records:
        d=record.data
        if d.get('forfeit'): continue
        own=next((p for p in d['players'] if p['userId']==user_id),None)
        if not own or own.get('withdrew') or len(own.get('people',[]))!=11: continue
        completed+=1; people.update(own['people'])
        under85+=d.get('preset')=='under-85'
        for rival in d['players']:
            if rival['userId'] and rival['userId']!=user_id and not rival.get('withdrew'):
                rivals[rival['userId']]+=1
                human_wins+=d.get('winner')==user_id
    return dict(completed=completed, humanWins=human_wins, under85=under85, players=len(people), rivalMatches=max(rivals.values(),default=0))

def award_match(session, user_ids, source):
    # Serialize cross-room progress updates so simultaneous completions cannot
    # miss a milestone. Always lock users in the same order.
    for user_id in sorted(set(user_ids)):
        session.scalar(select(User).where(User.id==user_id).with_for_update(key_share=True))
        progress=stats(session,user_id)
        for definition in ACHIEVEMENTS:
            if progress.get(definition['metric'],0)>=definition['target']:
                unlock(session,user_id,definition['code'],source)

def cup_standings(state):
    rows={p['id']:dict(id=p['id'],name=p['name'],played=0,won=0,points=0) for p in state['roster']}
    for f in state['fixtures']:
        if f['status']!='complete': continue
        for user_id in [f['a'],f['b']]: rows[user_id]['played']+=1
        if f.get('winner') in rows:
            row=rows[f['winner']]; row['won']+=1; row['points']+=2
        elif not f.get('forfeit'):
            for user_id in [f['a'],f['b']]: rows[user_id]['points']+=1
    result=sorted(rows.values(),key=lambda r:(-r['points'],r['name'].lower()))
    for row in result:
        row['rank']=1+sum(other['points']>row['points'] for other in result)
    return result

def settle_cup(session, room, winner, forfeit):
    cup_id=room.state.get('cupId')
    if not cup_id: return
    cup=session.scalar(select(Cup).where(Cup.id==cup_id).with_for_update())
    if not cup or cup.state['status']!='active': return
    state=copy.deepcopy(cup.state)
    fixture=next((f for f in state['fixtures'] if f.get('roomId')==room.id),None)
    if not fixture or fixture['status']=='complete': return
    fixture.update(status='complete',winner=winner,forfeit=forfeit)
    table=cup_standings(state)
    done=all(f['status']=='complete' for f in state['fixtures'])
    if len(state['roster'])==2 and table[0]['won']>=2:
        done=True
        for f in state['fixtures']:
            if f['status']=='pending': f['status']='not-needed'
    if done:
        state.update(status='complete',completedAt=now().isoformat(),winners=[r['id'] for r in table if r['rank']==1 and r['points']>0])
        for person in state['roster']:
            fixtures=[f for f in state['fixtures'] if person['id'] in [f['a'],f['b']] and f['status']!='not-needed']
            if fixtures and all(f['status']=='complete' and (not f.get('forfeit') or f.get('winner')==person['id']) for f in fixtures):
                unlock(session,person['id'],'cup-finisher',cup.id)
            if person['id'] in state['winners']: unlock(session,person['id'],'cup-champion',cup.id)
        session.add(Audit(action='cup.completed',resource=cup.id))
    cup.state=state

def save_record(session, source, data, group_id=None):
    stmt=insert(MatchArchive).values(id=source,group_id=group_id,data=data,created_at=now()).on_conflict_do_nothing(index_elements=['id']).returning(MatchArchive.id)
    if not session.scalar(stmt): return False
    users={p['userId'] for p in data['players'] if p['userId']}
    for user_id in users: session.add(MatchPlayer(match_id=source,user_id=user_id,won=data.get('winner')==user_id))
    session.flush()
    award_match(session,users,source)
    return True

def archive_room(session,room):
    if not any(m['status']=='complete' for m in room.state['matches']): return
    members={m['id']:m for m in room.state['members']}
    for user_id in sorted({m.get('userId',m.get('uid')) for m in members.values()}-{None}):
        session.scalar(select(User).where(User.id==user_id).with_for_update(key_share=True))
    for match in room.state['matches']:
        if match['status']!='complete': continue
        pair=[members[mid] for mid in [match['a'],match['b']] if mid in members]
        if len(pair)!=2: continue
        winner=members.get(match.get('winner'),{}).get('userId') or members.get(match.get('winner'),{}).get('uid')
        plan=match.get('plan') or match
        data=dict(kind='online',preset=room.state.get('preset'),competition=room.state.get('competition'),cupId=room.state.get('cupId'),rematch=bool(room.state.get('rematchOf')),forfeit=bool(match.get('forfeit')),winner=winner,
                  players=[dict(userId=m.get('userId',m.get('uid')),name=m['name'],withdrew=bool(m.get('forfeited') or (m.get('departed') and m.get('is_ai'))),people=sorted({person_key(p) for p in m['xi'].values()})) for m in pair],result=plan.get('result'),scorecards=plan.get('scorecards',[]))
        settle_cup(session,room,winner,data['forfeit'])
        save_record(session,'room:'+room.id+':'+match['id'],data,room.state.get('groupId'))

def archive_practice(session,game):
    state=game.state; match=state.get('match')
    if not match or state.get('abandoned') or state.get('forfeit'): return
    user=session.get(User,game.owner_id)
    data=dict(kind='practice',preset=state.get('preset'),competition=state.get('competition'),forfeit=False,winner=game.owner_id if match['result']['winner']=='you' else None,
              players=[dict(userId=game.owner_id,name='Guest player' if user.is_guest else user.username,people=sorted({person_key(p) for p in state['yourXI'].values()})),dict(userId=None,name='Practice AI',people=[])],result=match['result'],scorecards=match.get('scorecards',[]))
    save_record(session,'practice:'+game.id,data)

def engagement(session,cutoff):
    """Separate completed play on another day from immediate repeat clicks."""
    completed=[MatchArchive.created_at>=cutoff,MatchArchive.data['forfeit'].astext=='false']
    returning=select(MatchPlayer.user_id).join(MatchArchive).where(*completed).group_by(MatchPlayer.user_id).having(func.count(func.distinct(func.date(MatchArchive.created_at)))>=2).subquery()
    count=lambda query:session.scalar(query) or 0
    event_count=lambda action:count(select(func.count()).select_from(Audit).where(Audit.created_at>=cutoff,Audit.action==action))
    return dict(completedMatches=count(select(func.count()).select_from(MatchArchive).where(*completed)),
                returningPlayers=count(select(func.count()).select_from(returning)),
                practiceResultsViewed=event_count('game.result_viewed'),groupsCreated=event_count('group.created'),groupJoins=event_count('group.joined'),
                cupsStarted=event_count('cup.created'),cupsCompleted=event_count('cup.completed'),achievementShares=event_count('achievement.shared'),
                rematchesCompleted=count(select(func.count()).select_from(MatchArchive).where(*completed,MatchArchive.data['rematch'].astext=='true')))
