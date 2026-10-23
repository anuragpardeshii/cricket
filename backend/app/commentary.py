"""Over narratives built from recorded outcomes, without changing match randomness."""

def describe_over(*, contributions, dismissals, bowler, runs, wickets, deliveries, innings, total, total_wickets, balls, target=None):
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
        needed=target-total; remaining=max(0,120-balls)
        if needed<=0: parts.append(f"That seals the chase! Home with {10-total_wickets} wickets and {remaining} balls to spare.")
        elif total_wickets==10 or remaining==0:
            parts.append('Scores level! Nothing separates these teams.' if needed==1 else f"The defence holds! The chase falls {needed-1} runs short.")
        else:
            parts.append(f"Now {needed} needed from {remaining} balls."+(' Every delivery feels enormous!' if remaining<=30 or needed>remaining*2 else ' The chase is still alive.'))
    elif total_wickets==10 or balls>=120:
        parts.append(f"The innings closes at {total}/{total_wickets}. The chase will need {total+1}.")
    return ' '.join(parts)
