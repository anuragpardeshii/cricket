import copy
from app import match_review


def fixture():
    def card(side, runs, wickets, balls, batter_runs, faced):
        return dict(side=side, score=f'{runs}/{wickets} ({balls//6}.{balls%6})',
                    batting=[dict(name=side+' opener',runs=batter_runs,balls=faced,fours=10,sixes=2)],
                    bowling=[dict(name='Unused star',runs=0,balls=0,wickets=0),
                             dict(name='Active bowler',runs=runs,balls=balls,wickets=wickets)])
    cards=[card('you',150,6,120,145,120),card('opp',151,4,111,146,112)]
    squad={key:dict(name=key,role='AR',rating=85) for key in ['op1','op2','n3','n4','n5','ar','wk','b1','b2','b3','b4']}
    plan=dict(scorecards=cards,result=dict(winner='opp',margin='by 6 wickets, 9 balls to spare'),
              firstBatting='you',overs=20,timeline=[])
    return plan,dict(you=squad,opp=squad)


def analyze(plan,teams):
    return match_review.review(plan,teams,dict(you='A',opp='B'),match_review.VENUES[0],external=True)['result']['analysis']


def test_chase_uses_legal_overs_and_keeps_observations_separate_from_selection_advice():
    plan,teams=fixture();analysis=analyze(plan,teams)
    assert 'target of 151 in 18.3 overs' in analysis['decisive']
    assert analysis['metrics']['opp']['balls']==111  # Batter faced an additional no-ball.
    assert '6 wickets and 9 balls remaining' in analysis['teams'][1]['summary']
    assert any('5 extras' in n for n in analysis['teams'][1]['details'])
    assert 'Unused star' not in str(analysis)
    assert all(len(t['notes'])==2 for t in analysis['teams'])
    for claim in ['weak attack','exposed the lower order','Compare the five bowling options','famous XI','aggressive']:
        assert claim not in str(analysis)


def test_wicketless_attack_is_not_given_a_leading_wicket_taker():
    plan,teams=fixture()
    plan['scorecards'][1]['score']='151/0 (18.3)'
    plan['scorecards'][1]['bowling'][1]['wickets']=0
    analysis=analyze(plan,teams)
    assert 'Bowling: no bowler took a wicket.' in analysis['teams'][0]['notes']
    assert analysis['metrics']['you']['wicketsTaken']==0


def test_sparse_snapshots_do_not_invent_three_over_collapses_or_phase_totals():
    plan,teams=fixture()
    plan['timeline']=[dict(batting='you',over='OV 20',scorecards=[plan['scorecards'][0]])]
    analysis=analyze(plan,teams)
    assert 'between' not in analysis['decisive']
    assert not any(n.startswith('Overs ') for n in analysis['teams'][0]['details'])


def test_spell_and_phases_use_actual_score_differences_and_ball_intervals():
    plan,teams=fixture()
    for balls,runs,wickets in [(36,40,0),(72,80,0),(90,100,3),(120,150,6)]:
        card=copy.deepcopy(plan['scorecards'][0]);card['score']=f'{runs}/{wickets} ({balls//6}.{balls%6})'
        plan['timeline'].append(dict(batting='you',over=f'OV {balls//6}',scorecards=[card]))
    analysis=analyze(plan,teams)
    assert 'A lost 3 wickets for 20 runs between 12.0 and 15.0 overs' in analysis['collapses'][0]['lines'][0]
    assert len(analysis['collapses'][0]['lines'])==2
    assert '80/0 to 100/3' in analysis['collapses'][0]['lines'][1]
    details=analysis['teams'][0]['details']
    assert 'Overs 0.0–6.0: 40 runs, 0 wickets.' in details
    assert 'Overs 6.0–15.0: 60 runs, 3 wickets.' in details
    assert 'Overs 15.0–20.0: 50 runs, 3 wickets.' in details


def test_fantasy_tie_decision_does_not_invent_a_successful_chase():
    plan,teams=fixture();plan['scorecards'][1]['score']='150/4 (20.0)'
    plan['result'].update(tieResolution='match performance points',margin='after 12 tied attempts, decided by match performance points')
    analysis=analyze(plan,teams)
    assert 'Regulation scores were level' in analysis['decisive']
    assert 'reached the target' not in analysis['decisive']
    assert all('Scores finished level' in t['summary'] for t in analysis['teams'])


def test_two_line_collapse_reports_chase_equation_and_real_match_context():
    plan,teams=fixture()
    for balls,runs,wickets in [(72,80,0),(90,100,3),(111,151,4)]:
        card=copy.deepcopy(plan['scorecards'][1]);card['score']=f'{runs}/{wickets} ({balls//6}.{balls%6})'
        plan['timeline'].append(dict(batting='opp',over=f'OV {(balls+5)//6}',scorecards=[card]))
    analysis=analyze(plan,teams)
    fact=analysis['collapses'][0]
    assert fact['side']=='opp' and len(fact['lines'])==2
    assert 'still needed 51 from 30 balls with 7 wickets left' in fact['lines'][1]
    assert analysis['cricketFact']['title']=='2024 T20 World Cup final'
    assert analysis['cricketFact']['source'].startswith('https://www.icc-cricket.com/')


def test_named_contributions_include_support_and_victims_but_not_run_out_credit():
    plan,teams=fixture()
    plan['scorecards'][0]['batting']=[
        dict(name='Kohli',runs=70,balls=48,dismissal='b Starc'),
        dict(name='Rohit',runs=45,balls=30,dismissal='not out'),
        dict(name='Dhoni',runs=30,balls=25,dismissal='run out (Starc)')]
    plan['scorecards'][0]['bowling'][1]['name']='Starc'
    analysis=analyze(plan,teams)
    batting=analysis['teams'][0]['notes'][0]
    assert 'Kohli 70 from 48 balls' in batting
    assert 'Rohit 45 not out from 30 balls' in batting
    assert '145 of 150 team runs' in batting
    bowling=analysis['teams'][1]['notes'][1]
    assert 'dismissed Kohli' in bowling and 'Dhoni' not in bowling
    assert 'Active bowler' in str(analysis['teams'][0]['details'])


def test_legacy_review_refresh_preserves_scores_and_is_idempotent():
    plan,teams=fixture();analyze(plan,teams)
    analysis=plan['result']['analysis'];analysis.pop('namedReviewVersion')
    analysis['teams'][0]['notes']=['What worked: the leading batter and bowler above provided this XI’s strongest recorded contributions.']
    original=copy.deepcopy(plan)
    refreshed=match_review.refresh_named_review(copy.deepcopy(plan))
    assert 'you opener' in refreshed['result']['analysis']['teams'][0]['notes'][0]
    assert 'What worked:' not in str(refreshed)
    assert refreshed['scorecards']==original['scorecards']
    assert refreshed['result']['winner']==original['result']['winner']
    assert plan==original
    again=copy.deepcopy(refreshed)
    assert match_review.refresh_named_review(refreshed)==again


def test_collapse_names_only_batters_dismissed_inside_recorded_window():
    plan,teams=fixture()
    for balls,runs,wickets in [(72,80,1),(90,100,4)]:
        card=copy.deepcopy(plan['scorecards'][0]);card['score']=f'{runs}/{wickets} ({balls//6}.{balls%6})'
        card['batting']=[dict(name=name,runs=10,balls=10,dismissal='b Starc' if i==0 or balls==90 else 'not out')
                         for i,name in enumerate(['Earlier wicket','Kohli','Rohit','Dhoni'])]
        plan['timeline'].append(dict(batting='you',scorecards=[card]))
    fact=analyze(plan,teams)['collapses'][0]
    assert 'Dismissed: Kohli, Rohit, Dhoni.' in fact['lines'][0]
    assert 'Earlier wicket' not in str(fact)
    assert len(fact['lines'])==2


def test_practice_response_upgrades_legacy_notes_without_mutating_game():
    from types import SimpleNamespace
    from app.main import view
    plan,teams=fixture();analyze(plan,teams)
    plan['result']['analysis'].pop('namedReviewVersion')
    plan['result']['analysis']['teams'][0]['notes']=['What worked: generic conclusion']
    game=SimpleNamespace(id='test',version=1,state=dict(match=plan,opponentXI={}))
    original=copy.deepcopy(game.state)
    response=view(game)
    assert 'you opener' in response['state']['match']['result']['analysis']['teams'][0]['notes'][0]
    assert game.state==original
