import pytest
from app.commentary import describe_over


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
