"""Scorecard-grounded reviews. No external text generation or invented biographies."""
import secrets

SOURCE='https://www.iplt20.com/venues'
VENUES=[
    dict(id='wankhede',name='Wankhede Stadium',city='Mumbai',fact='Mumbai Indians play their home IPL cricket here.',source=SOURCE,condition='Batting surface',boundary=1.06,pace=1.02,spin=1.0),
    dict(id='chepauk',name='M. A. Chidambaram Stadium',city='Chennai',fact='This Chennai venue is the home of Chennai Super Kings.',source=SOURCE,condition='Spin-friendly surface',boundary=.96,pace=1.0,spin=1.08),
    dict(id='eden',name='Eden Gardens',city='Kolkata',fact='Eden Gardens is the home venue of Kolkata Knight Riders.',source=SOURCE,condition='Balanced surface',boundary=1.0,pace=1.0,spin=1.02),
    dict(id='chinnaswamy',name='M. Chinnaswamy Stadium',city='Bengaluru',fact='Royal Challengers Bengaluru are based at this venue.',source=SOURCE,condition='Batting surface',boundary=1.08,pace=1.0,spin=1.0),
    dict(id='ahmedabad',name='Narendra Modi Stadium',city='Ahmedabad',fact='This Ahmedabad venue hosts Gujarat Titans home matches.',source=SOURCE,condition='Balanced surface',boundary=1.0,pace=1.02,spin=1.02),
    dict(id='hyderabad',name='Rajiv Gandhi International Cricket Stadium',city='Hyderabad',fact='This is the home ground of Sunrisers Hyderabad.',source=SOURCE,condition='Batting surface',boundary=1.04,pace=1.0,spin=1.0),
]

INTERNATIONAL=[
    dict(id='lords',name="Lord's",city='London',fact='England won the 2019 ODI World Cup final here.',source='https://www.icc-cricket.com/tournaments/cricketworldcup/news/england-win-maiden-mens-world-cup-title-at-lords',condition='Seam-friendly surface',boundary=.98,pace=1.06,spin=1.0),
    dict(id='mcg',name='Melbourne Cricket Ground',city='Melbourne',fact='Australia won the 2015 ODI World Cup final at the MCG.',source='https://www.icc-cricket.com/tournaments/cricketworldcup/news/on-this-day-australia-win-icc-cwc-2015',condition='Balanced surface',boundary=.96,pace=1.02,spin=1.0),
    dict(id='scg',name='Sydney Cricket Ground',city='Sydney',fact='The SCG hosts the annual New Year Test and is home to the Sydney Sixers.',source='https://www.icc-cricket.com/news/scg-venue-x1208',condition='Spin-friendly surface',boundary=1.0,pace=1.0,spin=1.05),
]

def choose_venue(competition=None):
    return dict(secrets.choice(VENUES if competition=='ipl' else VENUES+INTERNATIONAL))

def skills(player):
    """Explicit role priors: an elite bowler is not automatically an elite batter."""
    rating=player['rating']; role=player['role']
    return dict(batting=rating if role in ('OP','BAT','WK') else rating-5 if role=='AR' else max(45,rating-30),
                bowling=rating if role in ('PACE','SPIN','AR') else max(40,rating-35))

def decisive(factory,names):
    """All formats replay tied regulation matches; bounded fantasy-game fallback."""
    from .commentary import describe_finish
    for attempt in range(12):
        plan=factory()
        if plan['result']['winner']!='tie':
            if attempt:
                plan['result']['fullMatchReplays']=attempt
                plan['result']['margin']+=f' after {attempt} full-match replay(s)'
                plan['timeline'][-1]['headline'],plan['timeline'][-1]['text']=describe_finish(plan['result'],plan['scorecards'],names)
            return plan
    # No fabricated runs: explicitly disclose the exceptional game-only decision.
    points={side:sum(p['points'] for p in plan['performances'] if p['side']==side) for side in ('you','opp')}
    winner=max(points,key=points.get) if points['you']!=points['opp'] else secrets.choice(['you','opp'])
    reason='match performance points' if points['you']!=points['opp'] else 'a random draw after equal performance points'
    plan['result'].update(winner=winner,margin=f'after 12 tied attempts, decided by {reason}',fullMatchReplays=11,tieResolution=reason)
    plan['timeline'][-1]['headline'],plan['timeline'][-1]['text']=describe_finish(plan['result'],plan['scorecards'],names)
    return plan

def wickets_lost(card):
    # Team totals include run-outs; bowler figures deliberately do not.
    return int(card['score'].split('/')[1].split()[0])

def review(plan,teams,names,venue,*,external=False):
    cards={c['side']:c for c in plan['scorecards']}
    metrics={}; reports=[]
    for side in ('you','opp'):
        own=cards[side]; against=cards['opp' if side=='you' else 'you']
        bat=own['batting']; bowl=against['bowling']
        bat_runs=sum(p['runs'] for p in bat)
        runs=int(own['score'].split('/')[0]); extras=max(0,runs-bat_runs); balls=sum(p['balls'] for p in bat)
        boundaries=sum(4*p.get('fours',0)+6*p.get('sixes',0) for p in bat)
        conceded=sum(p['runs'] for p in bowl); bowled=sum(p['balls'] for p in bowl)
        bowler_wickets=sum(p['wickets'] for p in bowl); wickets=wickets_lost(against)
        metrics[side]=dict(runs=runs,balls=balls,boundaryRuns=boundaries,wicketsTaken=wickets,economy=round(conceded*6/max(1,bowled),2))
        top=max(bat,key=lambda p:p['runs']); best=max(bowl,key=lambda p:(p['wickets'],-p['runs']/max(1,p['balls'])))
        squad=list(teams[side].values()); pace=sum(p['role']=='PACE' for p in squad); spin=sum(p['role']=='SPIN' for p in squad); ar=sum(p['role']=='AR' for p in squad)
        tail=sum(p['runs'] for p in bat[7:]); top3=sum(p['runs'] for p in bat[:3])
        notes=[f"{top['name']} supplied {top['runs']} from {top['balls']} balls; the top three contributed {top3} of {runs} runs and positions 8–11 added {tail}.",
               f"Boundaries supplied {boundaries} runs ({round(100*boundaries/max(1,runs))}% of the batting total). Batters added {bat_runs-boundaries} through non-boundary scoring; extras supplied {extras}.",
               f"{best['name']} was the leading wicket-taker with {best['wickets']}/{best['runs']}. The opposition lost {wickets} wickets ({bowler_wickets} credited to bowlers); bowling economy was {metrics[side]['economy']} runs per over.",
               f"XI balance: {pace} specialist pace bowlers, {spin} specialist spinners and {ar} all-rounder(s). These are card roles, not a claim about a player's unrecorded skills."]
        if not external:
            batting=round(sum(skills(p)['batting'] for p in squad[:7])/min(7,len(squad)),1)
            bowling=round(sum(skills(teams[side][k])['bowling'] for k in ['ar','b1','b2','b3','b4'])/5,1)
            notes.append(f"Model inputs: first seven batting strength {batting}; five-bowler strength {bowling}. Specialist bowlers have a lower batting prior; all-rounders contribute to both skills. Ratings influence probabilities, never guarantee the result.")
        evidence=[dict(name=p['name'],squad=p.get('squad',''),rating=p['rating'],**{k:v for k,v in p.get('ratingEvidence',{}).items() if k in ('note','source')}) for p in squad]
        reports.append(dict(side=side,name=names[side],outcome='Won' if plan['result']['winner']==side else 'Lost',notes=notes,players=evidence))
    for report in reports:
        side=report['side']; other='opp' if side=='you' else 'you'; m=metrics[side]; rival=metrics[other]
        phases=[]; last_runs=last_wickets=0
        for label,limit in [('Powerplay',10 if plan.get('overs')==50 else 6),('Middle overs',40 if plan.get('overs')==50 else 15),('Closing overs',plan.get('overs',20))]:
            samples=[e for e in plan['timeline'] if e.get('batting')==side and int(e['over'].split()[-1])<=limit]
            if not samples:continue
            snapshot=next((c for c in samples[-1].get('scorecards',[]) if c['side']==side),None)
            if not snapshot:continue
            total=int(snapshot['score'].split('/')[0]); lost=wickets_lost(snapshot)
            if total!=last_runs or lost!=last_wickets:phases.append(f"{label}: {total-last_runs} runs, {lost-last_wickets} wickets")
            last_runs,last_wickets=total,lost
        if phases:report['notes'].append('Innings phases — '+ '; '.join(phases)+'. Only phases actually reached are shown.')
        if m['boundaryRuns']>rival['boundaryRuns']:
            report['notes'].append(f"What worked: {m['boundaryRuns']-rival['boundaryRuns']} more runs from boundaries than the opponent. Boundary scoring alone does not decide a chase; wickets and the target still matter.")
        elif m['wicketsTaken']>rival['wicketsTaken']:
            report['notes'].append(f"What worked: the team took {m['wicketsTaken']-rival['wicketsTaken']} more wickets. This advantage did not by itself guarantee enough runs.")
        else:
            report['notes'].append('What worked: the leading batter and bowler above provided this XI’s strongest recorded contributions; the overall comparison did not show an edge in boundaries or wickets taken.')
        if side!=plan['result']['winner']:
            if rival['wicketsTaken']>=8:
                report['notes'].append(f"What hurt: losing {rival['wicketsTaken']} wickets exposed the lower order. Review batting depth alongside the bowling strength, especially if specialist bowlers are placed high in the batting order.")
            elif m['economy']>rival['economy']:
                report['notes'].append(f"What hurt: the attack conceded {m['economy']} per over versus {rival['economy']}. Compare the five bowling options in your next draft; the rates describe this match and may cover different innings lengths.")
            else:
                report['notes'].append('What hurt: the batting total did not win the contest despite that bowling economy. Review the scoring phases and batting order rather than assuming a famous XI must win.')
    winner=plan['result']['winner']; loser='opp' if winner=='you' else 'you'
    w,l=metrics[winner],metrics[loser]
    decisive_text=f"{names[winner]} won {plan['result']['margin']}. "
    if plan['firstBatting']==winner:
        decisive_text+=f"The chase finished {w['runs']-l['runs']} runs behind the first-innings total. "
    else:
        decisive_text+=f"The target was passed in {w['balls']//6}.{w['balls']%6} overs. "
    decisive_text+=f"Boundary runs were {w['boundaryRuns']} versus {l['boundaryRuns']}; wickets taken were {w['wicketsTaken']} versus {l['wicketsTaken']}. These are observed differences, not proof that a single selection caused the result."
    if plan['result'].get('tieResolution'):decisive_text=f"Regulation scores stayed level. {names[winner]} won {plan['result']['margin']}. The scorecard is unchanged; the fantasy-game decision is separate from runs scored."
    # Find a real wicket cluster from legal-ball progression in the losing innings.
    snapshots=[e for e in plan['timeline'] if e.get('batting')==loser]
    cluster=None
    for i,event in enumerate(snapshots):
        current=next((c for c in event.get('scorecards',[]) if c['side']==loser),None)
        previous=next((c for c in snapshots[max(0,i-3)].get('scorecards',[]) if c['side']==loser),None) if i>=3 else None
        if not current:continue
        lost=wickets_lost(current)-(wickets_lost(previous) if previous else 0)
        gained=int(current['score'].split('/')[0])-(int(previous['score'].split('/')[0]) if previous else 0)
        if lost>=2 and (cluster is None or lost>cluster[0]):cluster=(lost,gained,event['over'])
    if cluster:decisive_text+=f" A pressure spell ending at {cluster[2]} removed {cluster[0]} wickets for {cluster[1]} runs in at most three overs."
    public_venue={k:venue[k] for k in ('id','name','city','fact','source','condition')}
    condition_note='Venue shown for match atmosphere; this engine response does not provide evidence that the venue altered its probabilities.' if external else f"Fantasy surface settings: boundary weight ×{venue['boundary']}, pace wicket chance ×{venue['pace']}, spin wicket chance ×{venue['spin']}. These are game-design assumptions, not measured pitch forecasts; the same rules apply to both teams."
    plan['venue']=public_venue
    plan['result']['analysis']=dict(decisive=decisive_text,teams=reports,metrics=metrics,venue=public_venue,conditions=condition_note,
        method='Generated from this saved scorecard. Historical notes are sourced separately. A stronger XI can lose through match variation; no unobserved aggression, injury, dew or mentality is invented.')
    return plan
