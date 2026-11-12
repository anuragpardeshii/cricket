"""Decisive games in every format; historical ties remain readable."""
import copy
import pytest
from app import game, match_review, rooms, commentary
from app.progression import cup_standings


def plan(winner='tie'):
    return {'result': {'winner': winner,'margin':'scores level'}, 'overs': 50,
            'timeline': [{}], 'performances': [], 'scorecards': [
                {'side': side, 'batting': [{'runs': 10, 'balls': 6}], 'bowling': [{'wickets': 0}]}
                for side in ('you', 'opp')]}


def test_all_formats_replay_ties(monkeypatch):
    monkeypatch.setattr(commentary,'describe_finish',lambda *args:('Result','Replay decided'))
    for overs in (20,50):
        attempts=iter([plan(),plan('opp')]); calls=[]
        def once(*args,**kwargs):
            calls.append(args[5]); return next(attempts)
        monkeypatch.setattr(game,'_simulate_once',once)
        monkeypatch.setattr(match_review,'review',lambda result,*args:result)
        xi={slot['id']:{} for slot in game.SLOTS}
        result=game.simulate(xi,xi,overs=overs)
        assert result['result']['winner']=='opp' and result['result']['fullMatchReplays']==1
        assert calls==[overs,overs]


def test_repeated_ties_are_bounded_and_disclosed(monkeypatch):
    monkeypatch.setattr(commentary,'describe_finish',lambda *args:('Result','Decided'))
    calls=[]
    def factory():
        calls.append(True); result=plan()
        result['performances']=[{'side':'you','points':2},{'side':'opp','points':5}]
        return result
    result=match_review.decisive(factory,{'you':'A','opp':'B'})
    assert len(calls)==12 and result['result']['winner']=='opp'
    assert result['result']['tieResolution']=='match performance points'
    assert result['scorecards']==plan()['scorecards']


@pytest.mark.parametrize('forfeit,points', [(False, 1), (True, 0)])
def test_historical_ties_share_points_but_abandonments_do_not(forfeit, points):
    cup={'roster':[{'id':s,'name':s} for s in ('a','b')], 'fixtures':[{'a':'a','b':'b','status':'complete','winner':None,'forfeit':forfeit}]}
    assert [r['points'] for r in cup_standings(cup)]==[points,points]
    tournament={'members':cup['roster'],'matches':[dict(a='a',b='b',status='complete',winner=None,forfeit=forfeit,plan=copy.deepcopy(plan()))]}
    assert [r['points'] for r in rooms.standings(tournament)]==[points,points]
