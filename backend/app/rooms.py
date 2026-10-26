"""Transactional room state machine; all clocks and picks are server controlled."""
import copy
import itertools
import time
import math
from fastapi import HTTPException
from sqlalchemy import select
from .db import Room, Session, Audit, uid
from .catalog import load_catalog, SLOTS
from .game import simulate, rng, validate_order, match_overs
from .commentary import describe_finish
from .draft_pool import eligible_picks, person_key, used_people
from . import draft_turns

OVER_SECONDS=1
ODI_OVER_SECONDS=.5
AI_PICK_SECONDS=2

def playback_seconds(competition):
    """Seconds between visible over updates for a room match."""
    return ODI_OVER_SECONDS if competition=='odi' else OVER_SECONDS

def member(user_id,name): return dict(id=uid(),uid=user_id,userId=user_id,name=name,xi={},is_ai=user_id is None,ready=user_id is None,rerollsUsed=0,recentSquads=[])
def new_state(user_id,body):
    return dict(phase='lobby',format=body.format,capacity=body.capacity,seconds=body.pick_seconds,
                competition=getattr(body,'competition',None),edition=None,members=[member(user_id,body.name)],turn=0,draftRevision=0,deadline=None,matches=[],taken=[],champion=None,rolled=None,**draft_turns.initial())
def eligible(state,players):
    players=pool_players(state,players)
    teams=[m['xi'] for m in state['members']]
    return eligible_picks(teams,teams[state['turn']],players,SLOTS,state['taken'])

def pool_players(state,players):
    from .presets import filter_players
    players=filter_players(players,state.get('preset'))
    selected=state.get('competition')
    edition=state.get('edition')
    return [p for p in players if (not selected or p.get('competition')==selected)
            and (edition is None or p.get('edition')==edition)]

def start(state,ts):
    if state['phase']!='lobby': raise HTTPException(409,'Room already started')
    humans=[m for m in state['members'] if m['uid'] is not None]
    if state.get('cupId') and (len(humans)!=2 or {m['uid'] for m in humans}!=set(state['allowedUsers'])):
        raise HTTPException(409,'Both scheduled players must join this cup fixture; AI cannot replace them')
    if not humans or not all(m.get('ready',False) for m in humans):
        raise HTTPException(409,'Every human player must be ready before the host can start')
    # Bots are room members without a login identity; they cannot authenticate or act.
    number=1
    while len(state['members'])<state['capacity']:
        name=f'AI {number}'; number+=1
        if any(m['name'].lower()==name.lower() for m in state['members']): continue
        state['members'].append(member(None,name))
    state['phase']='draft'; state['rolled']=None; state['deadline']=ts+(AI_PICK_SECONDS if state['members'][state['turn']].get('is_ai') else state['seconds'])
    state['draftRevision']=state.get('draftRevision',0)+1

def roll(state,players,options=None,*,ts=None):
    if state['phase']!='draft': raise HTTPException(409,'Draft is not accepting rolls')
    players=pool_players(state,players)
    options=eligible(state,players) if options is None else options
    if not options: raise HTTPException(409,'No compatible player remains')
    current=state['members'][state['turn']]
    previous={p['id'] for p in (state.get('rolled') or {}).get('players',[])}
    if any(o['player']['id'] in previous for o in options):
        if current.get('rerollsUsed',0)>=3: raise HTTPException(409,'No rerolls left')
        current['rerollsUsed']=current.get('rerollsUsed',0)+1
    # Keep the whole squad visible; allowedSlots controls who can actually be picked.
    squads=sorted({o['player']['squad'] for o in options})
    recent=current.setdefault('recentSquads',[])
    fresh=[squad for squad in squads if squad not in recent[-3:]]
    repeated=[squad for squad in squads if squad in recent[-3:]]
    squad=rng.choice(fresh*5+repeated if fresh else squads)
    recent.append(squad)
    del recent[:-3]
    choices=[o for o in options if o['player']['squad']==squad]
    country,year=squad.rsplit(' ',1)
    allowed={}
    for option in choices: allowed.setdefault(option['player']['id'],[]).append(option['slot'])
    state['rolled']=dict(country=country,tournament=year,players=[p for p in players if p['squad']==squad],allowedSlots=allowed)
    state['draftRevision']=state.get('draftRevision',0)+1
    if ts is not None:
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
    state['draftRevision']=state.get('draftRevision',0)+1
    next_turn=draft_turns.after_pick(state,[m['xi'] for m in state['members']],state['turn'])
    if next_turn is None:
        state['phase']='live'; fixtures(state,ts); return
    state['turn']=next_turn
    state['deadline']=ts+(AI_PICK_SECONDS if state['members'][state['turn']].get('is_ai') else state['seconds'])

def kick_threshold(state):
    humans=sum(m['uid'] is not None for m in state['members'])
    return min(3,max(1,math.ceil(humans/2)))

def forfeit_match(state,match,ts):
    teams={m['id']:m for m in state['members']}
    available=[team for team in [match['a'],match['b']] if team in teams and not teams[team].get('forfeited')]
    winner=available[0] if len(available)==1 else None
    plan=match.pop('plan',None)
    interval=playback_seconds(state.get('competition'))
    count=max(0,int((ts-match.get('startedAt',ts))//interval))
    timeline=plan['timeline'][:count] if plan else []
    # Retain only overs already visible; never reveal the unused simulated result.
    match['timeline']=[{k:e[k] for k in ['over','innings','text','headline','kind','youScore','oppScore'] if k in e} for e in timeline]
    match['scores']={k:timeline[-1][k] if timeline else '—' for k in ['youScore','oppScore']}
    match['scorecards']=timeline[-1]['scorecards'] if timeline else []
    match['winner']=winner; match['status']='complete'; match['forfeit']=True
    match['result']=dict(winner='you' if winner==match['a'] and winner else 'opp' if winner else 'tie',margin='by forfeit' if winner else 'abandoned — both teams withdrew',mvp=None,highestScorer=None,bestBowler=None,yourScore=match['scores']['youScore'],opponentScore=match['scores']['oppScore'])
    match.pop('endsAt',None)

def remove_member(room,state,target,ts,reason):
    if target['uid'] is None: raise HTTPException(409,'This player has already left')
    removed_user=target['uid']
    target.setdefault('userId',removed_user)
    state.setdefault('removedUsers',[]).append(removed_user)
    target['uid']=None; target['departed']=True
    state['lastRemoval']=dict(name=target['name'],reason=reason)
    state['votes']={}  # A changed electorate starts fresh votes.
    if state.get('cupId') and state['phase']=='draft':
        target['forfeited']=True
        a,b=[m['id'] for m in state['members']]
        match=dict(id=uid(),round=1,a=a,b=b,status='pending',sources=[])
        state['matches']=[match]; forfeit_match(state,match,ts); state['phase']='live'
    elif state['phase'] in ['lobby','draft']:
        target['is_ai']=True
        if state['phase']=='draft' and state['members'][state['turn']]['id']==target['id']:
            state['deadline']=min(state['deadline'],ts+AI_PICK_SECONDS)
            state['draftRevision']=state.get('draftRevision',0)+1
    elif state['phase']=='live':
        target['forfeited']=True
        for match in state['matches']:
            if match['status']=='live' and target['id'] in [match['a'],match['b']]: forfeit_match(state,match,ts)
        launch_ready(state,ts)
    if room.owner_id==removed_user:
        successor=next((m['uid'] for m in state['members'] if m['uid'] is not None),None)
        if successor: room.owner_id=successor

def vote_kick(room,state,voter_id,target_id,ts):
    if state.get('cupId'): raise HTTPException(409,'Cup opponents cannot remove each other; you can withdraw instead')
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
    rng.shuffle(members)
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
    if state['format']=='league': rng.shuffle(matches)
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
        names={'you':teams[match['a']]['name'],'opp':teams[match['b']]['name']}
        match['plan']=simulate(teams[match['a']]['xi'],teams[match['b']]['xi'],teams[match['a']].get('order'),teams[match['b']].get('order'),team_names=names,overs=match_overs(state.get('competition')))
        result=match['plan']['result']
        if result['winner']=='tie':
            # Repeated six-ball tie-breaks, visible in the result.
            tie_scores=[]
            while True:
                a=sum(rng.choice([0,1,2,4,6]) for _ in range(6)); b=sum(rng.choice([0,1,2,4,6]) for _ in range(6))
                tie_scores.append(dict(a=a,b=b))
                if a!=b: break
            result['winner']='you' if a>b else 'opp'; result['margin']=f'after a six-ball tie-break ({a}–{b})'; result['tieBreaks']=tie_scores
            last=match['plan']['timeline'][-1]
            last['headline'],last['text']=describe_finish(result,match['plan']['scorecards'],names)
        match['winner']=match['a'] if result['winner']=='you' else match['b']
        interval=playback_seconds(state.get('competition'))
        match['status']='live'; match['startedAt']=ts; match['endsAt']=ts+interval*len(match['plan']['timeline'])

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
            innings_balls=match['plan'].get('overs',20)*6
            row['ballsFor']+=innings_balls if sum(p['wickets'] for p in own['bowling'])==10 else sum(p['balls'] for p in own['batting'])
            row['ballsAgainst']+=innings_balls if sum(p['wickets'] for p in against['bowling'])==10 else sum(p['balls'] for p in against['batting'])
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
    # Only the host starts a ready lobby; joining has no countdown.
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
    # Hidden simulations contain every scorecard snapshot. Do not clone them for
    # every viewer on every socket heartbeat just to discard them afterwards.
    state=copy.deepcopy({k:v for k,v in room.state.items() if k!='matches'})
    state['matches']=[]
    viewer=next((m for m in state['members'] if m['uid']==user_id),None)
    if not viewer: raise HTTPException(404,'Room not found')
    if state['phase']=='draft' and state['members'][state['turn']]['id']!=viewer['id']:
        state['rolled']=None
    if state.get('rolled'):
        used=used_people(m['xi'] for m in state['members'])
        state['rolled']['unavailableIds']=[p['id'] for p in state['rolled']['players'] if person_key(p) in used]
    state.pop('lobbyDeadline',None)
    votes=state.pop('votes',{})
    state.pop('removedUsers',None)
    state.pop('allowedUsers',None)
    state['kickRequired']=kick_threshold(state)
    for m in state['members']:
        m['kickVotes']=len(votes.get(m['id'],[])); m['voted']=viewer['id'] in votes.get(m['id'],[])
        m.pop('uid'); m.pop('userId',None); m.pop('recentSquads',None)
    for source in room.state['matches']:
        match=copy.deepcopy({k:v for k,v in source.items() if k!='plan'})
        state['matches'].append(match)
        plan=source.get('plan')
        if not plan: continue
        interval=playback_seconds(room.state.get('competition'))
        count=len(plan['timeline']) if match['status']=='complete' else max(0,min(len(plan['timeline']),int((ts-match['startedAt'])//interval)))
        match.pop('endsAt',None)
        match['timeline']=[{k:e[k] for k in ['over','innings','text','headline','kind','youScore','oppScore'] if k in e} for e in plan['timeline'][:count]]
        match['scores']={k:plan['timeline'][count-1][k] if count else '—' for k in ['youScore','oppScore']}
        if match['status']=='complete':
            match['result']=copy.deepcopy(plan['result']); match['scorecards']=copy.deepcopy(plan['scorecards'])
        else:
            match.pop('winner',None)
            match['scorecards']=copy.deepcopy(plan['timeline'][count-1]['scorecards']) if count else []
    return dict(id=room.id,code=room.code,visibility=room.visibility or 'private',version=room.version,serverTime=ts,you=viewer['id'],host=room.owner_id==user_id,state=state,standings=standings(room.state))

def tick():
    with Session() as session:
        ids=list(session.scalars(select(Room.id).where(Room.state['phase'].astext.in_(['draft','live']))))
        if not ids: return
    pools={}
    # One room per transaction: a tournament simulation must not hold the locks
    # of unrelated rooms while their players are trying to pick.
    for room_id in ids:
        with Session.begin() as session:
            room=session.scalar(select(Room).where(Room.id==room_id).with_for_update(skip_locked=True))
            if not room: continue
            ts=time.time(); current=room.state
            if current['phase']=='draft' and ts<current['deadline']: continue
            if current['phase']=='live' and not any(m['status']=='live' and ts>=m['endsAt'] for m in current['matches']): continue
            state=copy.deepcopy(room.state)
            players=[]
            if state['phase']=='draft':
                key=(state.get('competition'),state.get('edition'))
                if key not in pools:
                    pools[key]=[p for s in load_catalog(session,*key)['squads'] for p in s['players']]
                players=pools[key]
            if advance(state,players,ts):
                room.state=state; room.version+=1; session.add(Audit(action='room.clock',resource=room.id))
                from .progression import archive_room
                archive_room(session,room)
