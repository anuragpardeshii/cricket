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

def innings_totals(card):
    import re
    runs=int(card['score'].split('/')[0])
    over=re.search(r'\((\d+)\.([0-5])\)',card['score'])
    # Bowler balls exclude wides/no-balls; batter balls faced can differ.
    balls=int(over[1])*6+int(over[2]) if over else sum(p['balls'] for p in card['bowling'])
    return dict(runs=runs,wickets=wickets_lost(card),balls=balls)


def overs_text(balls):
    return f'{balls//6}.{balls%6}'


def innings_snapshots(plan,side):
    points={0:dict(runs=0,wickets=0,balls=0)}
    for event in plan['timeline']:
        if event.get('batting')!=side:continue
        card=next((c for c in event.get('scorecards',[]) if c['side']==side),None)
        if card:
            totals=innings_totals(card)
            points[totals['balls']]=totals
    return dict(sorted(points.items()))


def wicket_spell(points):
    candidates=[]
    for end,current in points.items():
        for start,previous in points.items():
            if not 0<end-start<=18:continue
            wickets=current['wickets']-previous['wickets']; runs=current['runs']-previous['runs']
            if wickets>=2 and runs>=0:candidates.append(dict(start=start,end=end,wickets=wickets,runs=runs))
    return max(candidates,key=lambda p:(p['wickets'],-p['runs']),default=None)


def phase_notes(plan,side,final):
    points=innings_snapshots(plan,side); notes=[]
    limits=[0,60,240,300] if plan.get('overs')==50 else [0,36,90,120]
    for start,limit in zip(limits,limits[1:]):
        end=min(limit,final['balls'])
        if end<=start or start not in points or end not in points:continue
        before,after=points[start],points[end]
        notes.append(f"Overs {overs_text(start)}–{overs_text(end)}: {after['runs']-before['runs']} runs, {after['wickets']-before['wickets']} wickets.")
    return notes


def review(plan,teams,names,venue,*,external=False):
    cards={c['side']:c for c in plan['scorecards']}
    totals={side:innings_totals(card) for side,card in cards.items()}
    metrics={}; reports=[]
    winner=plan['result']['winner']; loser='opp' if winner=='you' else 'you'
    first=plan['firstBatting']; chase='opp' if first=='you' else 'you'
    target=totals[first]['runs']+1
    tied=bool(plan['result'].get('tieResolution'))
    for side in ('you','opp'):
        other='opp' if side=='you' else 'you'
        own=cards[side]; against=cards[other]; m=totals[side]
        bat=own['batting']; bowl=[p for p in against['bowling'] if p['balls']>0 or p['wickets']>0 or p['runs']>0]
        bat_runs=sum(p['runs'] for p in bat); extras=max(0,m['runs']-bat_runs)
        boundaries=sum(4*p.get('fours',0)+6*p.get('sixes',0) for p in bat)
        conceded=sum(p['runs'] for p in bowl); bowled=sum(p['balls'] for p in bowl)
        bowler_wickets=sum(p['wickets'] for p in bowl)
        economy=round(conceded*6/bowled,2) if bowled else None
        metrics[side]=dict(runs=m['runs'],balls=m['balls'],boundaryRuns=boundaries,wicketsTaken=totals[other]['wickets'],economy=economy)
        top=max(bat,key=lambda p:(p['runs'],p['balls']),default=None)
        best=max(bowl,key=lambda p:(p['wickets'],-p['runs']/max(1,p['balls'])),default=None)
        notes=[]
        if top and top['runs']:
            notes.append(f"Batting: {top['name']} top-scored with {top['runs']} from {top['balls']} balls, contributing {round(100*top['runs']/max(1,m['runs']))}% of the total.")
        else:notes.append('Batting: no batter scored a run.')
        if best and best['wickets']:
            notes.append(f"Bowling: {best['name']} took {best['wickets']}/{best['runs']} in {overs_text(best['balls'])} overs.")
        else:notes.append('Bowling: no bowler took a wicket.')
        if tied:
            summary='Scores finished level. The winner was selected by the disclosed fantasy-game tie rule.'
        elif side==chase:
            if side==winner:
                summary=f"Reached the target of {target} with {10-m['wickets']} wickets and {max(0,plan.get('overs',20)*6-m['balls'])} balls remaining."
            else:
                ending='all out' if m['wickets']==10 else f"{m['runs']}/{m['wickets']}"
                summary=f"Chasing {target}, finished {ending}, needing {target-m['runs']} more runs to win."
        elif side==winner:
            summary=f"Defended {m['runs']}: {names[other]} finished on {totals[other]['runs']}/{totals[other]['wickets']}."
        else:
            summary=f"Could not defend {m['runs']}: {names[other]} reached the target with {10-totals[other]['wickets']} wickets remaining."
        squad=list(teams[side].values())
        pace=sum(p['role']=='PACE' for p in squad); spin=sum(p['role']=='SPIN' for p in squad); ar=sum(p['role']=='AR' for p in squad)
        details=[f"Scoring: {boundaries} boundary runs, {bat_runs-boundaries} other batter runs and {extras} extras.",
                 f"The opposition lost {totals[other]['wickets']} wickets ({bowler_wickets} credited to bowlers)." + (f" Bowling economy: {economy} runs per over, excluding byes and leg-byes." if economy is not None else ''),
                 f"Top three: {sum(p['runs'] for p in bat[:3])} runs. Positions 8–11: {sum(p['runs'] for p in bat[7:])} runs." if any(p['balls'] or p['runs'] for p in bat[7:]) else f"Top three: {sum(p['runs'] for p in bat[:3])} runs. Positions 8–11 did not face a ball or score.",
                 f"XI roles: {pace} specialist pace bowlers, {spin} specialist spinners, {ar} all-rounder(s). Role counts alone do not establish which XI is better balanced."]
        details.extend(phase_notes(plan,side,m))
        if not external:
            batting=round(sum(skills(p)['batting'] for p in squad[:7])/max(1,min(7,len(squad))),1)
            bowling=round(sum(skills(teams[side][k])['bowling'] for k in ['ar','b1','b2','b3','b4'])/5,1)
            details.append(f"Model inputs: first-seven batting strength {batting}; five-bowler strength {bowling}. These game estimates affect probabilities, not guaranteed outcomes.")
        evidence=[dict(name=p['name'],squad=p.get('squad',''),rating=p['rating'],**{k:v for k,v in p.get('ratingEvidence',{}).items() if k in ('note','source')}) for p in squad]
        reports.append(dict(side=side,name=names[side],outcome='Won' if winner==side else 'Lost',summary=summary,notes=notes,details=details,players=evidence))
    decisive_text=f"{names[winner]} won {plan['result']['margin']}. "
    if tied:
        decisive_text+='Regulation scores were level; this was a fantasy-game tie decision, not a win on runs or wickets.'
    else:
        if winner==chase:
            decisive_text+=f"They reached the target of {target} in {overs_text(totals[chase]['balls'])} overs."
        else:
            decisive_text+=f"{names[chase]} finished {totals[chase]['runs']}/{totals[chase]['wickets']} chasing {target}."
        spell=wicket_spell(innings_snapshots(plan,loser))
        if spell:
            decisive_text+=f" {names[loser]} lost {spell['wickets']} wickets for {spell['runs']} runs between {overs_text(spell['start'])} and {overs_text(spell['end'])} overs."
    public_venue={k:venue[k] for k in ('id','name','city','fact','source','condition')}
    condition_note='Venue shown for match atmosphere; this engine response does not provide evidence that the venue altered its probabilities.' if external else f"Fantasy surface settings: boundary weight ×{venue['boundary']}, pace wicket chance ×{venue['pace']}, spin wicket chance ×{venue['spin']}. These are game-design assumptions, not measured pitch forecasts; the same rules apply to both teams."
    plan['venue']=public_venue
    plan['result']['analysis']=dict(decisive=decisive_text,teams=reports,metrics=metrics,venue=public_venue,conditions=condition_note,
        method='Based on the saved scorecard. Contributions and scoring spells describe this match; they do not prove a player or selection caused the loss. Historical season evidence and model assumptions are shown separately.')
    return plan
