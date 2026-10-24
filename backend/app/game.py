import secrets
import time
from fastapi import HTTPException
from .catalog import SLOTS
from .draft_pool import squads_for, person_key, used_people
from .commentary import MatchHighlights, describe_finish
rng = secrets.SystemRandom()
AI_PICK_SECONDS = 3
def initial(competition=None, edition=None):
    return dict(competition=competition,edition=edition,screen='draft', yourXI={}, opponentXI={}, taken={}, rolled=None, rerollsUsed=0, turn='you', pickNumber=1, match=None)
def fits(state,p):
    return p['id'] not in state['taken'] and person_key(p) not in used_people([state['yourXI'],state['opponentXI']]) and any(s['id'] not in state['yourXI'] and p['role'] in s['accepts'] for s in SLOTS)
def validate_order(order):
    if not isinstance(order,list) or len(order)!=11 or set(order)!={s['id'] for s in SLOTS}:
        raise HTTPException(422,'Formation must contain each of the eleven team positions exactly once')
    return list(order)

def act(state, action, player_id=None, slot_id=None, *, squads, order=None):
    squads=squads_for(squads,state.get('competition'),state.get('edition'))
    if state.get('abandoned'): raise HTTPException(409,'This practice game has ended')
    if action=='exit':
        state['abandoned']=True; state['screen']='landing'
        if state.get('match'):
            state['match']['result']['winner']='opp'; state['match']['result']['margin']='by forfeit'
        return
    if action=='formation':
        if state['screen']!='draft': raise HTTPException(409,'Formation is locked once the match starts')
        state['order']=validate_order(order); return
    if action == 'start':
        if state['screen'] != 'lobby': raise HTTPException(409,'Draft already started')
        state['screen']='draft'
        return
    if action == 'match':
        if state['match']: return
        if len(state['yourXI']) != 11 or len(state['opponentXI']) != 11: raise HTTPException(409,'Complete both teams first')
        state['match']=simulate(state['yourXI'],state['opponentXI'],state.get('order'))
        state['screen']='match'
        return
    if state['screen'] != 'draft' or state['turn'] != 'you': raise HTTPException(409,'Wait for your turn to pick')
    if action == 'roll':
        if state['rolled'] and any(fits(state,p) for p in state['rolled']['players']):
            if state['rerollsUsed'] >= 3: raise HTTPException(409,'No rerolls left')
            state['rerollsUsed'] += 1
        pool=[s for s in squads if any(fits(state,p) for p in s['players'])]
        if not pool: raise HTTPException(409, 'No eligible players in catalog')
        state['rolled']=rng.choice(pool)
        return
    slot=next((s for s in SLOTS if s['id']==slot_id),None)
    player=next((p for p in (state['rolled'] or {}).get('players',[]) if p['id']==player_id),None)
    if not slot or not player or not fits(state,player) or slot_id in state['yourXI'] or player['role'] not in slot['accepts']:
        raise HTTPException(409,'Player or slot unavailable')
    state['yourXI'][slot_id]=player
    state['taken'][player_id]=True
    state['rolled']=None
    state['pickNumber']+=1
    state['turn']='opp'
    state['aiDeadline']=time.time()+AI_PICK_SECONDS

def advance(state, squads, ts):
    if state.get('abandoned') or state['screen']!='draft' or state['turn']!='opp' or ts<state.get('aiDeadline',float('inf')):
        return False
    squads=squads_for(squads,state.get('competition'),state.get('edition'))
    used=used_people([state['yourXI'],state['opponentXI']])
    slot=rng.choice([s for s in SLOTS if s['id'] not in state['opponentXI']])
    candidates=sorted([p for squad in squads for p in squad['players'] if p['id'] not in state['taken'] and person_key(p) not in used and p['role'] in slot['accepts']],key=lambda p:-p['rating'])
    if not candidates: raise HTTPException(409, 'No eligible opponent players in catalog')
    opponent=rng.choice(candidates[:5])
    state['opponentXI'][slot['id']]=opponent
    state['taken'][opponent['id']]=True
    state['pickNumber']+=1
    state['turn']='done' if len(state['yourXI'])==11 else 'you'
    state.pop('aiDeadline',None)
    return True

def advance_game(session, game):
    import copy
    from .catalog import load_catalog
    from .db import Audit
    state=copy.deepcopy(game.state)
    if state.get('turn')!='opp' or state.get('abandoned'): return False
    if advance(state,load_catalog(session,state.get('competition'),state.get('edition'))['squads'],time.time()):
        game.state=state; game.version+=1
        session.add(Audit(action='game.ai_pick',resource=game.id))
        return True
    return False

def tick():
    from sqlalchemy import select
    from .db import Session, Game
    with Session.begin() as session:
        games=session.scalars(select(Game).where(Game.state['screen'].astext=='draft',Game.state['turn'].astext=='opp').with_for_update(skip_locked=True).limit(50)).all()
        for game in games: advance_game(session,game)

def simulate(you,opp,you_order=None,opp_order=None,team_names=None):
    import copy
    first=rng.choice(['you','opp']); second='opp' if first=='you' else 'you'
    teams={'you':you,'opp':opp}; scores={'you':'—','opp':'—'}; timeline=[]; scorecards=[]
    first_runs=0
    for num,side in enumerate([first,second],1):
        highlights=MatchHighlights(); partnership=0
        other_side='opp' if side=='you' else 'you'
        order=(you_order if side=='you' else opp_order) or [s['id'] for s in SLOTS]
        batters=[teams[side][slot] for slot in order]
        fielders=list(teams[other_side].values())
        bowlers=[teams[other_side][k] for k in ['ar','b1','b2','b3','b4']]
        batting=[dict(id=p['id'],name=p['name'],runs=0,balls=0,fours=0,sixes=0,dismissal='did not bat',side=side) for p in batters]
        bowling=[dict(id=p['id'],name=p['name'],balls=0,runs=0,wickets=0,maidens=0,side=other_side) for p in bowlers]
        runs=wickets=balls=0; striker=0; non=1; nxt=2
        batting[0]['dismissal']=batting[1]['dismissal']='not out'
        for over in range(20):
            start=runs; lines=[]; deliveries=[]; contributions={}; dismissals=[]; fell=False
            bowler=bowlers[over%5]; bc=bowling[over%5]; over_wickets=0
            for ball in range(6):
                if wickets==10 or (num==2 and runs>first_runs): break
                batter=batters[striker]; card=batting[striker]
                card['balls']+=1; balls+=1; bc['balls']+=1
                contribution=contributions.setdefault(batter['name'],dict(runs=0,sixes=0,fours=0))
                if rng.random()<max(.02,min(.095,.048+(bowler['rating']-batter['rating'])*.0018)):
                    wickets+=1; bc['wickets']+=1; over_wickets+=1; fell=True
                    fielder=rng.choice(fielders); caught=rng.random()<.7
                    card['dismissal']=f"c {fielder['name']} b {bowler['name']}" if caught else f"b {bowler['name']}"
                    text=f"{bowler['name']} deceived {batter['name']}, caught by {fielder['name']} for {card['runs']}" if caught else f"{bowler['name']} bowled {batter['name']} for {card['runs']}"
                    dismissals.append(dict(text=text,name=batter['name'],runs=card['runs'])); partnership=0
                    deliveries.append('W'); lines.append(dict(kind='wicket',text=f'{over}.{ball+1} — {text}.'))
                    if nxt<11:
                        striker=nxt; nxt+=1; batting[striker]['dismissal']='not out'
                else:
                    scored=rng.choices([0,1,2,4,6],[30,36,9,max(2,13+(batter['rating']-85)*.5),max(1,5+(batter['rating']-85)*.35)])[0]
                    runs+=scored; card['runs']+=scored; bc['runs']+=scored; contribution['runs']+=scored; deliveries.append(str(scored))
                    partnership+=scored
                    if scored in (4,6):
                        key='fours' if scored==4 else 'sixes'; card[key]+=1; contribution[key]+=1
                    lines.append(dict(kind='six' if scored==6 else 'four' if scored==4 else 'info',text=f"{over}.{ball+1} — {batter['name']}: {scored} run{'s' if scored!=1 else ''}."))
                    if scored%2: striker,non=non,striker
            if runs==start and len(deliveries)==6: bc['maidens']+=1
            striker,non=non,striker
            scores[side]=f'{runs}/{wickets} ({balls//6}.{balls%6})'
            headline,narrative=highlights.over(number=over+1,batting=batting,bowler=bowler['name'],contributions=contributions,dismissals=dismissals,runs=runs-start,total=runs,wickets=wickets,balls=balls,target=first_runs+1 if num==2 else None,partnership=partnership,partners=[batters[striker]['name'],batters[non]['name']])
            current=dict(side=side,score=scores[side],batting=copy.deepcopy(batting),bowling=copy.deepcopy(bowling))
            # Finished innings cards are immutable; reuse them until serialization.
            timeline.append(dict(over=f'OV {over+1}',kind='over',headline=headline,text=narrative,lines=lines,deliveries=deliveries,wicket=fell,bar=dict(runs=runs-start,wicket=fell,innings=num),batting=side,innings=num,youScore=scores['you'],oppScore=scores['opp'],scorecards=list(scorecards)+[current]))
            if wickets==10 or (num==2 and runs>first_runs): break
        scorecards.append(current)
        if num==1: first_runs=runs
    winner=second if runs>first_runs else first if runs<first_runs else 'tie'
    margin=f'by {10-wickets} wickets, {120-balls} balls to spare' if runs>first_runs else f'by {first_runs-runs} runs' if runs<first_runs else 'scores level'
    bats=[p for c in scorecards for p in c['batting']]; bowls=[p for c in scorecards for p in c['bowling']]
    top=max(bats,key=lambda p:(p['runs'],-p['balls'])); best_bowler=max([p for p in bowls if p['balls']>0],key=lambda p:(p['wickets'],-p['runs']))
    performances={}
    for p in bats:
        performances[(p['side'],p['id'])]=dict(id=p['id'],name=p['name'],side=p['side'],runs=p['runs'],wickets=0,points=p['runs'])
    for p in bowls:
        perf=performances[(p['side'],p['id'])]; perf['wickets']=p['wickets']; perf['points']+=25*p['wickets']
    mvp=max(performances.values(),key=lambda p:p['points'])
    award=lambda p,line: dict(id=p['id'],name=p['name'],side=p['side'],line=line)
    result=dict(winner=winner,margin=margin,mvp=award(mvp,f"{mvp['runs']} runs · {mvp['wickets']} wickets"),highestScorer=award(top,f"{top['runs']} ({top['balls']})"),bestBowler=award(best_bowler,f"{best_bowler['wickets']}/{best_bowler['runs']}"),yourScore=scores['you'],opponentScore=scores['opp'])
    timeline[-1]['headline'],timeline[-1]['text']=describe_finish(result,scorecards,team_names or {'you':'Your team','opp':'AI'})
    timeline[-1]['kind']='result'
    return dict(timeline=timeline,result=result,firstBatting=first,scorecards=scorecards,performances=list(performances.values()))
