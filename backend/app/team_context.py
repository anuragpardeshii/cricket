"""Transparent fantasy rules for the lightweight simulator, not fitted career statistics."""
import math
from .match_review import skills

BATTING_ROLES={'OP','BAT','WK','AR'}
BOWLING_ROLES={'AR','PACE','SPIN'}


def composition(xi,order):
    players=[xi[key] for key in order]
    return dict(battingDepth=sum(p['role'] in BATTING_ROLES for p in players),
                topOrderBatters=sum(p['role'] in BATTING_ROLES for p in players[:5]),
                openersInOpeningPair=sum(p['role']=='OP' for p in players[:2]),
                bowlingOptions=sum(p['role'] in BOWLING_ROLES for p in players),
                paceOptions=sum(p['role']=='PACE' for p in players),
                spinOptions=sum(p['role']=='SPIN' for p in players),
                allRounders=sum(p['role']=='AR' for p in players))


def bowling_phase_bonus(player,over,overs):
    # Role-based assumptions; historical phase specialisms are not in these cards.
    early=over<(10 if overs==50 else 6); late=over>=(40 if overs==50 else 15)
    if player['role']=='PACE':return 2.0 if early or late else 0.0
    if player['role']=='SPIN':return 2.5 if not early and not late else -1.0
    return 0.0


def choose_bowler(players,used,previous,over,overs,venue,form,rng):
    quota=overs//5; left=overs-over-1
    options=[]; weights=[]
    for player in players:
        pid=player['id']
        if pid==previous or used[pid]>=quota:continue
        remaining={p['id']:quota-used[p['id']]-(p['id']==pid) for p in players}
        if sum(min(n,left//2 if key==pid else (left+1)//2) for key,n in remaining.items())<left:continue
        surface=venue.get('spin',1) if player['role']=='SPIN' else venue.get('pace',1) if player['role']=='PACE' else 1
        quality=skills(player)['bowling']+form[pid]+bowling_phase_bonus(player,over,overs)+20*(surface-1)
        options.append(player);weights.append(math.exp((quality-80)/12))
    if not options:raise ValueError('The bowling attack cannot cover the remaining overs')
    selected=rng.choices(options,weights=weights)[0]
    used[selected['id']]+=1
    return selected


def delivery_model(batter,bowler,*,position,faced,remaining_batters,wickets,runs,balls,overs,target,venue,bat_form=0,bowl_form=0):
    batting=skills(batter)['batting']+bat_form
    bowling=skills(bowler)['bowling']+bowl_form+bowling_phase_bonus(bowler,balls//6,overs)
    # Opening role fit is deliberately small; batting order still determines who faces balls.
    if position<2 and batter['role']=='OP':batting+=2
    elif position<2 and batter['role'] in ('PACE','SPIN'):batting-=4
    depth=sum(p['role'] in BATTING_ROLES for p in remaining_batters)
    remaining=max(1,overs*6-balls)
    if target is not None:
        required=max(0,target-runs)*6/remaining
        par=(5.2 if overs==50 else 7.5)*max(.7,min(1.3,1+(batting-bowling)/100))
        intent=max(-.12,min(.35,(required/par-1)*.22))
    else:
        intent=.16 if balls>=overs*6*.75 else 0.0
    # An exposed tail reduces discretionary risk; a difficult chase can still force it.
    intent-=.08 if wickets>=4 and depth<=1 else 0
    if depth>=3 and wickets<=6:intent+=.025
    settled=.90 if faced<5 else 1.0 if faced<20 else 1.06
    surface=venue.get('spin',1) if bowler['role']=='SPIN' else venue.get('pace',1) if bowler['role']=='PACE' else (venue.get('pace',1)+venue.get('spin',1))/2
    wicket=max(.015,min(.12,((.034 if overs==50 else .048)+(bowling-batting)*.0015)*surface*(1+intent*.7)))
    boundary=venue.get('boundary',1)*settled*(1+intent)
    # Bowling quality influences scoring as well as dismissals.
    edge=(batting-bowling)*.13
    weights=[max(12,30-edge-intent*14+(1-settled)*20),36,9,
             max(2,13+(batting-85)*.32+edge)*boundary,
             max(1,5+(batting-85)*.22+edge*.4)*boundary]
    return wicket,weights
