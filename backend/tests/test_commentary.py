import pytest
from app.commentary import describe_over
from app.commentary import MatchHighlights, describe_finish


def commentary(**overrides):
    data=dict(contributions={'MS Dhoni':dict(runs=4,sixes=0,fours=0)},dismissals=[],bowler='T Boult',runs=4,wickets=0,deliveries=6,innings=1,total=54,total_wickets=2,balls=60)
    data.update(overrides)
    return describe_over(**data)


def test_boundaries_and_dismissal_are_grounded_in_the_over():
    text=commentary(contributions={'MS Dhoni':dict(runs=18,sixes=3,fours=0)},dismissals=['T Boult deceived MS Dhoni, caught by K Williamson for 42'],runs=18,wickets=1)
    assert 'MS Dhoni launches 3 sixes' in text
    assert 'caught by K Williamson for 42' in text
    assert '18 runs, 1 wicket' in text
    assert 'hits back!' in text and 'four' not in text


def test_quiet_over_stays_dramatic_without_inventing_boundaries_or_wickets():
    text=commentary()
    assert 'Every run is a battle' in text and 'MS Dhoni works hard for 4 runs' in text
    assert '4 runs, 0 wickets' in text
    assert 'sixes' not in text and 'Gone!' not in text


@pytest.mark.parametrize('deliveries,maiden',[(6,True),(3,False)])
def test_maiden_requires_six_deliveries(deliveries,maiden):
    text=commentary(contributions={'MS Dhoni':dict(runs=0,sixes=0,fours=0)},runs=0,deliveries=deliveries)
    assert ('Six balls. Not a run!' in text)==maiden


@pytest.mark.parametrize('total,wickets,balls,expected',[
    (102,5,115,'Home with 5 wickets and 5 balls to spare.'),
    (90,7,114,'Now 11 needed from 6 balls.'),
    (100,8,120,'Scores level!'),
    (90,10,114,'The chase falls 10 runs short.'),
])
def test_chase_context_uses_actual_target_and_remaining_balls(total,wickets,balls,expected):
    assert expected in commentary(innings=2,total=total,total_wickets=wickets,balls=balls,target=101)


def highlight_data(**overrides):
    data=dict(number=1,batting=[dict(id='rohit',name='R Sharma',runs=12,balls=4),dict(id='virat',name='V Kohli',runs=3,balls=2)],
              bowler='R Ashwin',contributions={'R Sharma':dict(runs=12)},dismissals=[],runs=15,total=15,wickets=0,balls=6,target=None,partnership=15,partners=['R Sharma','V Kohli'])
    data.update(overrides)
    return data


def test_highlights_follow_partnership_breakthrough_and_pressure():
    highlights=MatchHighlights()
    title,text=highlights.over(**highlight_data())
    assert title=='The opening act' and 'R Sharma and V Kohli' in text and 'contributing 12' in text
    assert highlights.over(**highlight_data(number=2,runs=5))==('','')
    title,text=highlights.over(**highlight_data(number=4,partnership=54,total=54))
    assert title=='A partnership takes charge' and 'put on 54 together' in text
    title,text=highlights.over(**highlight_data(number=7,total=72,wickets=1,partnership=0,dismissals=[dict(name='R Sharma',runs=41,text='R Ashwin bowled R Sharma for 41')]))
    assert title=='The big wicket' and 'R Ashwin bowled R Sharma for 41' in text
    highlights.over(**highlight_data(number=9,bowler='J Bumrah',runs=3))
    title,text=highlights.over(**highlight_data(number=10,bowler='R Ashwin',runs=2))
    assert 'J Bumrah and R Ashwin concede just 5' in text
    assert 'wicket' not in text # Tight bowling is not an invented dismissal.


def test_highlights_have_a_budget_and_always_include_the_ending():
    highlights=MatchHighlights(); texts=[]
    for over in range(1,21):
        title,text=highlights.over(**highlight_data(number=over,runs=20,total=over*20,balls=over*6))
        if text: texts.append(text)
    assert 2<=len(texts)<=6
    assert 'innings closes at 400/0' in texts[-1]
    assert all(len(text.split())<=55 for text in texts)


def test_chase_highlight_knows_only_current_equation():
    title,text=MatchHighlights().over(**highlight_data(number=16,runs=7,total=139,balls=96,target=170,partnership=10))
    assert title=='The chase reaches its crossroads'
    assert '31 needed from 24 balls' in text and 'wins' not in text


def test_finish_credits_winners_batters_and_actual_bowlers():
    cards=[dict(side='you',batting=[dict(name='I Kishan',runs=70)],bowling=[dict(name='J Anderson',wickets=2,runs=40)]),
           dict(side='opp',batting=[dict(name='J Root',runs=80)],bowling=[dict(name='R Ashwin',wickets=3,runs=24)])]
    title,text=describe_finish(dict(winner='you',margin='by 4 wickets'),cards,{'you':'India','opp':'England'})
    assert 'India wins by 4 wickets' in text and 'I Kishan supplies 70 runs' in text
    assert 'R Ashwin takes 3/24 with the ball' in text
    assert 'J Root' not in text and 'J Anderson' not in text
