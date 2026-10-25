"""Over narratives built from recorded outcomes, without changing match randomness."""

class MatchHighlights:
    """Select a few story beats using only events already played in this innings."""

    def __init__(self, overs=20):
        self.count=0
        self.overs=overs
        self.last_over=-3
        self.previous=None
        self.milestones=set()
        self.pressure_reported=False
        self.partnership_reported=False

    def over(self, *, number, batting, bowler, contributions, dismissals, runs,
             total, wickets, balls, target, partnership, partners):
        ball_limit=self.overs*6
        finished=wickets==10 or balls>=ball_limit or (target is not None and total>=target)
        previous=self.previous
        self.previous=(bowler,runs)
        headline=text=''
        if finished:
            if target is None:
                leader=max(batting,key=lambda p:p['runs'])
                headline='The target is set'
                text=f"{leader['name']} leads the scoring with {leader['runs']} from {leader['balls']}. The innings closes at {total}/{wickets} — the chase needs {total+1}."
            else:
                # The simulator replaces this with the actual result and heroes.
                headline='The final act'; text='The final ball of the contest has been played.'
        elif number==1:
            a,b=batting[:2]
            headline='The opening act'
            text=f"{a['name']} and {b['name']} open the innings. "
            if dismissals:
                text+=f"An early twist! {dismissals[0]['text']}."
            elif total>=12:
                leader=max([a,b],key=lambda p:p['runs'])
                text+=f"Straight onto the attack: {total} from the first over, with {leader['name']} contributing {leader['runs']}."
            else:
                text+=f"{bowler} opens the bowling; the first exchange ends at {total}/{wickets}."
        elif self.count<5 and number-self.last_over>=3:
            big_wicket=next((d for d in dismissals if d['runs']>=25),None)
            fifty=next((p for p in batting if p['runs']>=50 and p['id'] not in self.milestones),None)
            if len(dismissals)>=2:
                headline='The innings jolts'
                names=' and '.join(d['name'] for d in dismissals[:2])
                text=f"How quickly this game turns! {bowler} removes {names}; {len(dismissals)} wickets in one over leave the batting side at {total}/{wickets}."
            elif big_wicket:
                headline='The big wicket'
                text=f"Just when {big_wicket['name']} was building something! {big_wicket['text']}. At {total}/{wickets}, the batting side must find a new driving force."
            elif partnership>=50 and not self.partnership_reported:
                headline='A partnership takes charge'
                self.partnership_reported=True
                text=f"{partners[0]} and {partners[1]} have put on {partnership} together. The stand is giving the innings its shape — {total}/{wickets}, and the bowlers need a way back."
            elif fifty:
                headline='A fifty to savour'
                text=f"{fifty['name']} reaches {fifty['runs']} from {fifty['balls']} balls. The innings has its anchor; now comes the chance to turn that platform into something bigger."
            elif runs>=16:
                leader=max(contributions,key=lambda name:contributions[name]['runs'])
                headline='The attack breaks loose'
                text=f"{leader} takes on {bowler}, scoring {contributions[leader]['runs']} of the over’s {runs} runs. A sudden burst of intent — the score races to {total}/{wickets}!"
            elif number==(10 if self.overs==50 else 6):
                leader=max(batting,key=lambda p:p['runs'])
                headline='Powerplay verdict'
                threshold=80 if self.overs==50 else 50
                period='ten' if self.overs==50 else 'six'
                mood='A flying start!' if total>=threshold and wickets<=2 else 'Early damage to repair.' if wickets>=3 else 'The opening exchanges are over.'
                text=f"{mood} {total}/{wickets} after {period}, with {leader['name']} making {leader['runs']} from {leader['balls']}. The middle overs will test that platform."
            elif previous and previous[1]+runs<=8:
                headline='The bowlers tighten the grip'
                text=f"{previous[0]} and {bowler} concede just {previous[1]+runs} across two overs. The runs have dried up — who can break the pressure at {total}/{wickets}?"
            elif target is not None and balls>=ball_limit-24 and not self.pressure_reported:
                self.pressure_reported=True
                headline='The chase reaches its crossroads'
                text=f"Still {target-total} needed from {ball_limit-balls} balls, with {10-wickets} wickets in hand. Every boundary can change this chase; every dot gives the fielding side another breath."
        if text:
            self.count+=1; self.last_over=number
            self.milestones.update(p['id'] for p in batting if p['runs']>=50)
        return headline,text


def describe_finish(result, scorecards, team_names):
    """Final-only narrative: credit players on the winning side, in their roles."""
    winner=result['winner']
    if winner=='tie': return 'Nothing separates them!', 'Scores level after both innings. Neither side has found the winning edge.'
    batting=next(c['batting'] for c in scorecards if c['side']==winner)
    bowling=next(c['bowling'] for c in scorecards if c['side']!=winner)
    batter=max(batting,key=lambda p:p['runs'])
    bowler=max(bowling,key=lambda p:(p['wickets'],-p['runs']))
    text=f"{team_names[winner]} wins {result['margin']}! {batter['name']} supplies {batter['runs']} runs"
    if bowler['wickets']:
        text+=f", while {bowler['name']} takes {bowler['wickets']}/{bowler['runs']} with the ball."
    else:
        text+=f"; the winning side’s bowlers finish without a wicket."
    return 'The final act',text

def describe_over(*, contributions, dismissals, bowler, runs, wickets, deliveries, innings, total, total_wickets, balls, target=None, overs=20):
    sixes=sum(c['sixes'] for c in contributions.values())
    if wickets>=2 and runs>=12:
        opening='Absolute drama! Big hits and wickets collide in a breathless over.'
    elif runs==0 and deliveries==6:
        opening='A wicket-maiden! Not a run conceded, and a breakthrough to go with it.' if wickets else 'Six balls. Not a run! The pressure is building.'
    elif wickets>=2:
        opening='The innings is on the ropes! Multiple wickets turn this over on its head.'
    elif wickets:
        opening='A twist in the tale! The bowler finds a way through.'
    elif sixes>=3:
        opening='What an onslaught! The sixes just keep coming.'
    elif runs>=15:
        opening='The batting side cuts loose! A huge over shifts the momentum.'
    elif runs<=4:
        opening='Every run is a battle. The bowler keeps a tight grip on this over.'
    else:
        opening='The contest keeps simmering. Both sides are fighting for the next opening.'
    parts=[opening]
    for name,c in contributions.items():
        shots=[]
        if c['sixes']: shots.append(f"launches {c['sixes']} six{'es' if c['sixes']!=1 else ''}")
        if c['fours']: shots.append(f"cracks {c['fours']} four{'s' if c['fours']!=1 else ''}")
        if shots: parts.append(f"{name} {' and '.join(shots)}, scoring {c['runs']} runs in the over.")
        elif c['runs']: parts.append(f"{name} works hard for {c['runs']} run{'s' if c['runs']!=1 else ''}.")
        elif not dismissals: parts.append(f"{name} cannot find a run.")
    if dismissals:
        parts.append(('But the bowler hits back! ' if sixes or any(c['fours'] for c in contributions.values()) else 'Gone! ')+'. '.join(dismissals)+'.')
    parts.append(f"{runs} run{'s' if runs!=1 else ''}, {wickets} wicket{'s' if wickets!=1 else ''} from {bowler}’s {'over' if deliveries==6 else str(deliveries)+'-ball spell'}.")
    if innings==2 and target is not None:
        needed=target-total; remaining=max(0,overs*6-balls)
        if needed<=0: parts.append(f"That seals the chase! Home with {10-total_wickets} wickets and {remaining} balls to spare.")
        elif total_wickets==10 or remaining==0:
            parts.append('Scores level! Nothing separates these teams.' if needed==1 else f"The defence holds! The chase falls {needed-1} runs short.")
        else:
            parts.append(f"Now {needed} needed from {remaining} balls."+(' Every delivery feels enormous!' if remaining<=30 or needed>remaining*2 else ' The chase is still alive.'))
    elif total_wickets==10 or balls>=overs*6:
        parts.append(f"The innings closes at {total}/{total_wickets}. The chase will need {total+1}.")
    return ' '.join(parts)
