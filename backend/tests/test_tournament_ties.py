import copy

import pytest

from app import rooms
from app.progression import cup_standings


def state(format='league'):
    return {'format': format, 'competition': 'odi', 'members': [
        {'id': side, 'name': side.upper(), 'xi': {}, 'order': []} for side in ('a', 'b')
    ], 'matches': [{'id': 'm', 'a': 'a', 'b': 'b', 'status': 'pending', 'sources': []}]}


def plan(winner='tie'):
    return {'result': {'winner': winner}, 'overs': 50,
            'timeline': [{}], 'performances': [], 'scorecards': [
                {'side': side, 'batting': [{'runs': 10, 'balls': 6}], 'bowling': [{'wickets': 0}]}
                for side in ('you', 'opp')]}


def test_league_tie_starts_without_replay_and_shares_points(monkeypatch):
    calls = []
    def simulate(*args, **kwargs):
        calls.append(kwargs)
        return plan()
    monkeypatch.setattr(rooms, 'simulate', simulate)
    tournament = state()
    rooms.launch_ready(tournament, 100)
    match = tournament['matches'][0]
    assert len(calls) == 1 and calls[0]['overs'] == 50
    assert match['winner'] is None and match['status'] == 'live'
    assert match['endsAt'] == 100.5
    match['status'] = 'complete'
    assert [(r['points'], r['won'], r['played']) for r in rooms.standings(tournament)] == [(1, 0, 1)] * 2


def test_knockout_replays_full_match_and_advances_winner(monkeypatch):
    plans = iter([plan(), plan('opp')])
    monkeypatch.setattr(rooms, 'simulate', lambda *args, **kwargs: next(plans))
    tournament = state('knockout')
    rooms.launch_ready(tournament, 100)
    match = tournament['matches'][0]
    assert match['winner'] == 'b'
    assert match['plan']['result']['fullMatchReplays'] == 1
    assert 'tieBreaks' not in match['plan']['result']


def test_repeated_knockout_ties_are_bounded(monkeypatch):
    calls = []
    def simulate(*args, **kwargs):
        calls.append(True)
        result = plan()
        result['performances'] = [{'side': 'you', 'points': 2}, {'side': 'opp', 'points': 5}]
        return result
    monkeypatch.setattr(rooms, 'simulate', simulate)
    monkeypatch.setattr(rooms, 'describe_finish', lambda *args: ('Finished', 'B advances'))
    tournament = state('knockout')
    rooms.launch_ready(tournament, 100)
    match = tournament['matches'][0]
    assert len(calls) == 12 and match['winner'] == 'b'
    assert match['plan']['timeline'][-1]['text'] == 'B advances'


@pytest.mark.parametrize('forfeit,points', [(False, 1), (True, 0)])
def test_ties_share_cup_points_but_abandonments_do_not(forfeit, points):
    cup = {'roster': [{'id': side, 'name': side} for side in ('a', 'b')],
           'fixtures': [{'a': 'a', 'b': 'b', 'status': 'complete', 'winner': None, 'forfeit': forfeit}]}
    assert [r['points'] for r in cup_standings(cup)] == [points, points]
    tournament = state()
    match = tournament['matches'][0]
    match.update(status='complete', winner=None, forfeit=forfeit, plan=copy.deepcopy(plan()))
    assert [r['points'] for r in rooms.standings(tournament)] == [points, points]
