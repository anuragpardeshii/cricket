import random
from collections import Counter
import pytest
from app import game, match_review, team_context


def team(prefix,rating=85):
    roles=['OP','OP','BAT','BAT','BAT','AR','WK','PACE','PACE','SPIN','SPIN']
    return {slot['id']:dict(id=f'{prefix}-{i}',name=f'{prefix} {i}',role=roles[i],rating=rating) for i,slot in enumerate(game.SLOTS)}


def distribution(**changes):
    args=dict(position=0,faced=12,remaining_batters=[dict(role='BAT')]*3,wickets=4,runs=80,balls=72,overs=20,target=None,venue=dict(boundary=1,pace=1,spin=1))
    args.update(changes)
    return team_context.delivery_model(dict(role='OP',rating=85),dict(role='PACE',rating=85),**args)


def test_depth_settling_and_chase_risk_change_deliveries_at_identical_ratings():
    deep=distribution();tail=distribution(remaining_batters=[dict(role='PACE')]*3)
    assert deep[0]>tail[0] and deep[1][-1]>tail[1][-1]  # Depth permits risk; exposed tail conserves wickets.
    new=distribution(faced=0);settled=distribution(faced=25)
    assert settled[1][-1]>new[1][-1] and settled[1][0]<new[1][0]
    easy=distribution(target=100);hard=distribution(target=200)
    assert hard[0]>easy[0] and hard[1][-1]>easy[1][-1]
    opening=distribution(position=0);middle=distribution(position=3)
    assert opening[0]<middle[0]  # Same card, different batting-order fit.
    assert distribution(overs=50)[0]<distribution(overs=20)[0]  # Format-specific risk baseline.


@pytest.mark.parametrize('overs',[20,50])
@pytest.mark.parametrize('extra',[False,True])
def test_bowling_attack_covers_full_innings_without_consecutive_overs_or_exceeding_quota(overs,extra):
    xi=team('a');players=[p for p in xi.values() if p['role'] in team_context.BOWLING_ROLES]
    if extra:players.append(dict(id='sixth',role='AR',rating=85))
    for seed in range(12):
        used={p['id']:0 for p in players};form={p['id']:0 for p in players};previous=None;rng=random.Random(seed)
        for over in range(overs):
            bowler=team_context.choose_bowler(players,used,previous,over,overs,{},form,rng)
            assert bowler['id']!=previous
            previous=bowler['id']
        assert sum(used.values())==overs and max(used.values())<=overs//5


def test_varied_bowling_roles_receive_different_phase_and_pitch_opportunities():
    pace=dict(id='p',role='PACE',rating=85);spin=dict(id='s',role='SPIN',rating=85)
    assert team_context.bowling_phase_bonus(pace,0,20)>team_context.bowling_phase_bonus(spin,0,20)
    assert team_context.bowling_phase_bonus(spin,8,20)>team_context.bowling_phase_bonus(pace,8,20)
    args=dict(position=2,faced=12,remaining_batters=[],wickets=1,runs=70,balls=48,overs=20,target=None)
    neutral=team_context.delivery_model(dict(role='BAT',rating=85),spin,**args,venue={'spin':1})
    dry=team_context.delivery_model(dict(role='BAT',rating=85),spin,**args,venue={'spin':1.08})
    assert dry[0]>neutral[0]


@pytest.mark.parametrize('overs',[20,50])
def test_complete_simulation_keeps_scorecard_and_context_consistent(monkeypatch,overs):
    monkeypatch.setattr(game,'rng',random.Random(45))
    plan=game.simulate(team('a'),team('b'),overs=overs)
    assert plan['model']['version']=='local-context-v1'
    assert plan['model']['teams']['you']['openersInOpeningPair']==2
    for card in plan['scorecards']:
        total=match_review.innings_totals(card)
        assert total['runs']==sum(p['runs'] for p in card['batting'])==sum(p['runs'] for p in card['bowling'])
        assert total['wickets']==sum(p['wickets'] for p in card['bowling'])
        assert total['balls']==sum(p['balls'] for p in card['bowling'])
        assert all(p['balls']<=overs//5*6 for p in card['bowling'])
    assert plan['result']['winner'] in ('you','opp')


def test_higher_ratings_do_not_guarantee_wins_and_order_changes_the_simulation(monkeypatch):
    low,high=team('a',85),team('b',90);wins=Counter()
    order=list(high);poor_order=order[7:]+order[:7]
    different=0
    for seed in range(24):
        monkeypatch.setattr(game,'rng',random.Random(seed))
        regular=game._simulate_once(low,high,venue=match_review.VENUES[0])
        wins[regular['result']['winner']]+=1
        monkeypatch.setattr(game,'rng',random.Random(seed))
        unbalanced=game._simulate_once(low,high,opp_order=poor_order,venue=match_review.VENUES[0])
        different+=regular['result']['opponentScore']!=unbalanced['result']['opponentScore']
        assert unbalanced['model']['teams']['opp']['topOrderBatters']<regular['model']['teams']['opp']['topOrderBatters']
    assert wins['you']>0 and wins['opp']>0
    assert different>20
