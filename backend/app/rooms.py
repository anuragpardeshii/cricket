"""Transactional room state machine; all clocks and picks are server controlled."""
import copy
import itertools
import time
import math
from fastapi import HTTPException
from sqlalchemy import select
from .db import Room, Session, Audit, uid
from .catalog import load_catalog, SLOTS
from .game import simulate, rng, validate_order

OVER_SECONDS=3
AI_PICK_SECONDS=2

def member(user_id,name): return dict(id=uid(),uid=user_id,name=name,xi={},is_ai=user_id is None,rerollsUsed=0)
def new_state(user_id,body):
    return dict(phase='lobby',format=body.format,capacity=body.capacity,seconds=body.pick_seconds,
                lobbyDeadline=time.time()+body.lobby_minutes*60,members=[member(user_id,body.name)],turn=0,deadline=None,matches=[],taken=[],champion=None,rolled=None)
def eligible(state,players):
    current=state['members'][state['turn']]; output=[]
    for p in players:
        if p['id'] in state['taken']: continue
        for slot in SLOTS:
            if slot['id'] in current['xi'] or p['role'] not in slot['accepts']: continue
            # Reserve sufficient specialists for all remaining teams.
            remaining=[s for m in state['members'] for s in SLOTS if s['id'] not in m['xi'] and not (m is current and s['id']==slot['id'])]
            available=[q for q in players if q['id'] not in state['taken'] and q['id']!=p['id']]
            groups=[({'OP'},lambda s:s['id'].startswith('op')),({'OP','BAT'},lambda s:s['id'].startswith('op') or s['id'].startswith('n')),({'AR'},lambda s:s['id']=='ar'),({'WK'},lambda s:s['id']=='wk'),({'PACE','SPIN'},lambda s:s['id'].startswith('b'))]
            if all(sum(q['role'] in roles for q in available)>=sum(test(s) for s in remaining) for roles,test in groups):
                output.append(dict(player=p,slot=slot['id']))
    return output

def start(state,ts):
    if state['phase']!='lobby': raise HTTPException(409,'Room already started')
    # Bots are room members without a login identity; they cannot authenticate or act.
    number=1
    while len(state['members'])<state['capacity']:
        name=f'AI {number}'; number+=1
        if any(m['name'].lower()==name.lower() for m in state['members']): continue
        state['members'].append(member(None,name))
    state['phase']='draft'; state['rolled']=None; state['deadline']=ts+(AI_PICK_SECONDS if state['members'][state['turn']].get('is_ai') else state['seconds'])

def roll(state,players,options=None,*,ts=None):
    if state['phase']!='draft': raise HTTPException(409,'Draft is not accepting rolls')
    options=eligible(state,players) if options is None else options
    if not options: raise HTTPException(409,'No compatible player remains')
    current=state['members'][state['turn']]
    previous={p['id'] for p in (state.get('rolled') or {}).get('players',[])}
    if any(o['player']['id'] in previous for o in options):
        if current.get('rerollsUsed',0)>=3: raise HTTPException(409,'No rerolls left')
        current['rerollsUsed']=current.get('rerollsUsed',0)+1
    # Keep the whole squad visible; allowedSlots controls who can actually be picked.
    squad=rng.choice(sorted({o['player']['squad'] for o in options}))
    choices=[o for o in options if o['player']['squad']==squad]
    country,year=squad.rsplit(' ',1)
    allowed={}
    for option in choices: allowed.setdefault(option['player']['id'],[]).append(option['slot'])
    state['rolled']=dict(country=country,tournament=year,players=[p for p in players if p['squad']==squad],allowedSlots=allowed)
    if previous and ts is not None:
        state['deadline']=ts+state['seconds']

def pick(state,players,ts,player_id=None,slot_id=None,automatic=False):
    options=eligible(state,players)
    if not options: raise HTTPException(409,'No compatible player remains')
    rolled={p['id'] for p in (state.get('rolled') or {}).get('players',[])}
    if automatic and not any(o['player']['id'] in rolled for o in options):
        roll(state,players,options)
        rolled={p['id'] for p in state['rolled']['players']}
    if not rolled: raise HTTPException(409,'Roll a squad before picking a player')
    options=[o for o in options if o['player']['id'] in rolled]
    choice=rng.choice(options) if automatic else next((o for o in options if o['player']['id']==player_id and o['slot']==slot_id),None)
    if not choice: raise HTTPException(409,'Player or slot unavailable')
    m=state['members'][state['turn']]; m['xi'][choice['slot']]=choice['player']; state['taken'].append(choice['player']['id'])
    state['lastPick']=dict(name=m['name'],player=choice['player']['name'],automatic=automatic,is_ai=m.get('is_ai',False))
    state['rolled']=None
    if all(len(m['xi'])==11 for m in state['members']):
        state['phase']='live'; fixtures(state,ts); return
    state['turn']=(state['turn']+1)%len(state['members'])
    state['deadline']=ts+(AI_PICK_SECONDS if state['members'][state['turn']].get('is_ai') else state['seconds'])

def kick_threshold(state):
    humans=sum(m['uid'] is not None for m in state['members'])
    return min(3,max(1,math.ceil(humans/2)))

def forfeit_match(state,match,ts):
    teams={m['id']:m for m in state['members']}
    available=[team for team in [match['a'],match['b']] if team in teams and not teams[team].get('forfeited')]
    winner=available[0] if len(available)==1 else None
    plan=match.pop('plan',None)
    count=max(0,int((ts-match.get('startedAt',ts))//OVER_SECONDS))
    timeline=plan['timeline'][:count] if plan else []
    # Retain only overs already visible; never reveal the unused simulated result.
    match['timeline']=[{k:e[k] for k in ['over','innings','text','youScore','oppScore']} for e in timeline]
    match['scores']={k:timeline[-1][k] if timeline else '—' for k in ['youScore','oppScore']}
    match['scorecards']=timeline[-1]['scorecards'] if timeline else []
    match['winner']=winner; match['status']='complete'; match['forfeit']=True
    match['result']=dict(winner='you' if winner==match['a'] and winner else 'opp' if winner else 'tie',margin='by forfeit' if winner else 'abandoned — both teams withdrew',mvp=None,highestScorer=None,bestBowler=None,yourScore=match['scores']['youScore'],opponentScore=match['scores']['oppScore'])
    match.pop('endsAt',None)

def remove_member(room,state,target,ts,reason):
    if target['uid'] is None: raise HTTPException(409,'This player has already left')
    removed_user=target['uid']
    state.setdefault('removedUsers',[]).append(removed_user)
    target['uid']=None; target['departed']=True
    state['lastRemoval']=dict(name=target['name'],reason=reason)
    state['votes']={}  # A changed electorate starts fresh votes.
    if state['phase'] in ['lobby','draft']:
        target['is_ai']=True
        if state['phase']=='draft' and state['members'][state['turn']]['id']==target['id']:
            state['deadline']=min(state['deadline'],ts+AI_PICK_SECONDS)
    elif state['phase']=='live':
        target['forfeited']=True
        for match in state['matches']:
            if match['status']=='live' and target['id'] in [match['a'],match['b']]: forfeit_match(state,match,ts)
        launch_ready(state,ts)
    if room.owner_id==removed_user:
        successor=next((m['uid'] for m in state['members'] if m['uid'] is not None),None)
        if successor: room.owner_id=successor

def vote_kick(room,state,voter_id,target_id,ts):
    if state['phase'] not in ['lobby','draft','live']: raise HTTPException(409,'Voting is closed')
    voter=next(m for m in state['members'] if m['uid']==voter_id)
    target=next((m for m in state['members'] if m['id']==target_id and m['uid'] is not None),None)
    if not target or target['id']==voter['id']: raise HTTPException(409,'Choose another active human player')
    votes=state.setdefault('votes',{}).setdefault(target_id,[])
    if voter['id'] in votes: raise HTTPException(409,'You already voted to remove this player')
    votes.append(voter['id'])
    passed=len(votes)>=kick_threshold(state)
    if passed: remove_member(room,state,target,ts,'kicked')
    return passed

def fixtures(state,ts):
    members=[m['id'] for m in state['members']]
    matches=[]
    if state['format']=='league':
        for a,b in itertools.combinations(members,2): matches.append(dict(id=uid(),round=1,a=a,b=b,status='pending',sources=[]))
    else:
        round_num=1
        for i in range(0,len(members),2): matches.append(dict(id=uid(),round=1,a=members[i],b=members[i+1],status='pending',sources=[]))
        previous=list(matches)
        while len(previous)>1:
            round_num+=1; current=[]
            for i in range(0,len(previous),2): current.append(dict(id=uid(),round=round_num,a=None,b=None,status='pending',sources=[previous[i]['id'],previous[i+1]['id']]))
            matches+=current; previous=current
    state['matches']=matches
    launch_ready(state,ts)

def launch_ready(state,ts):
    teams={m['id']:m for m in state['members']}; matches={m['id']:m for m in state['matches']}
    for match in state['matches']:
        if match['status']!='pending': continue
        if match['sources']:
            parents=[matches[k] for k in match['sources']]
            if not all(p['status']=='complete' for p in parents): continue
            match['a'],match['b']=[p['winner'] for p in parents]
        if any(team not in teams or teams[team].get('forfeited') for team in [match['a'],match['b']]):
            forfeit_match(state,match,ts); continue
        match['plan']=simulate(teams[match['a']]['xi'],teams[match['b']]['xi'],teams[match['a']].get('order'),teams[match['b']].get('order'))
        result=match['plan']['result']
        if result['winner']=='tie':
            # Repeated six-ball tie-breaks, visible in the result.
            tie_scores=[]
            while True:
                a=sum(rng.choice([0,1,2,4,6]) for _ in range(6)); b=sum(rng.choice([0,1,2,4,6]) for _ in range(6))
                tie_scores.append(dict(a=a,b=b))
                if a!=b: break
            result['winner']='you' if a>b else 'opp'; result['margin']=f'after a six-ball tie-break ({a}–{b})'; result['tieBreaks']=tie_scores
        match['winner']=match['a'] if result['winner']=='you' else match['b']
        match['status']='live'; match['startedAt']=ts; match['endsAt']=ts+OVER_SECONDS*len(match['plan']['timeline'])

def standings(state):
    rows={m['id']:dict(id=m['id'],name=m['name'],played=0,won=0,points=0,runsFor=0,ballsFor=0,runsAgainst=0,ballsAgainst=0) for m in state['members']}
    for match in state['matches']:
        if match['status']!='complete': continue
        for side,key,other in [('you','a','b'),('opp','b','a')]:
            if match[key] not in rows: continue
            row=rows[match[key]]; row['played']+=1
            if match['winner']==match[key]: row['won']+=1; row['points']+=2
            if match.get('forfeit'): continue
            cards=match['plan']['scorecards']; own=next(c for c in cards if c['side']==side); against=next(c for c in cards if c['side']!=side)
            row['runsFor']+=sum(p['runs'] for p in own['batting']); row['runsAgainst']+=sum(p['runs'] for p in against['batting'])
            row['ballsFor']+=120 if sum(p['wickets'] for p in own['bowling'])==10 else sum(p['balls'] for p in own['batting'])
            row['ballsAgainst']+=120 if sum(p['wickets'] for p in against['bowling'])==10 else sum(p['balls'] for p in against['batting'])
    for row in rows.values(): row['nrr']=round(6*row['runsFor']/max(1,row['ballsFor'])-6*row['runsAgainst']/max(1,row['ballsAgainst']),3)
    return sorted(rows.values(),key=lambda r:(-r['points'],-r['nrr'],r['id']))

def tournament_award(state):
    totals={}
    for match in state['matches']:
        if match['status']!='complete' or match.get('forfeit'): continue
        for p in match['plan']['performances']:
            team=match['a'] if p['side']=='you' else match['b']; key=(team,p['id'])
            row=totals.setdefault(key,dict(name=p['name'],team=team,runs=0,wickets=0,points=0))
            for field in ['runs','wickets','points']: row[field]+=p[field]
    return max(totals.values(),key=lambda p:p['points']) if totals else None

def advance(state,players,ts):
    changed=False
    if state['phase']=='lobby' and ts>=state['lobbyDeadline']:
        start(state,state['lobbyDeadline'])
        changed=True
    while state['phase']=='draft' and ts>=state['deadline']:
        pick(state,players,state['deadline'],automatic=True); changed=True
    if state['phase']=='live':
        # Catch up multiple rounds after worker downtime without rerolling results.
        while True:
            due=[m for m in state['matches'] if m['status']=='live' and ts>=m['endsAt']]
            if not due: break
            for m in due: m['status']='complete'
            changed=True
            launch_ready(state,max(m['endsAt'] for m in due))
        if all(m['status']=='complete' for m in state['matches']):
            state['phase']='complete'
            active={m['id'] for m in state['members'] if not m.get('forfeited')}
            leaders=[r for r in standings(state) if r['id'] in active]
            state['champion']=state['matches'][-1]['winner'] if state['format']=='knockout' else (leaders[0]['id'] if leaders else None)
            state['award']=tournament_award(state); changed=True
    return changed

def project(room,user_id,ts):
    state=copy.deepcopy(room.state); viewer=next((m for m in state['members'] if m['uid']==user_id),None)
    if not viewer: raise HTTPException(404,'Room not found')
    votes=state.pop('votes',{})
    state.pop('removedUsers',None)
    state['kickRequired']=kick_threshold(state)
    for m in state['members']:
        m['kickVotes']=len(votes.get(m['id'],[])); m['voted']=viewer['id'] in votes.get(m['id'],[])
        m.pop('uid')
    for match in state['matches']:
        plan=match.pop('plan',None)
        if not plan: continue
        count=len(plan['timeline']) if match['status']=='complete' else max(0,min(len(plan['timeline']),int((ts-match['startedAt'])//OVER_SECONDS)))
        match.pop('endsAt',None)
        match['timeline']=[{k:e[k] for k in ['over','innings','text','youScore','oppScore']} for e in plan['timeline'][:count]]
        match['scores']={k:plan['timeline'][count-1][k] if count else '—' for k in ['youScore','oppScore']}
        if match['status']=='complete':
            match['result']=plan['result']; match['scorecards']=plan['scorecards']
        else: match.pop('winner',None)
    return dict(id=room.id,code=room.code,visibility=room.visibility or 'private',version=room.version,serverTime=ts,you=viewer['id'],host=room.owner_id==user_id,state=state,standings=standings(room.state))

def tick():
    with Session.begin() as session:
        rooms=session.scalars(select(Room).where(Room.state['phase'].astext.in_(['lobby','draft','live'])).with_for_update(skip_locked=True).limit(50)).all()
        if not rooms: return
        players=[p for s in load_catalog(session)['squads'] for p in s['players']]
        for room in rooms:
            state=copy.deepcopy(room.state)
            if advance(state,players,time.time()):
                room.state=state; room.version+=1; session.add(Audit(action='room.clock',resource=room.id))
