import copy
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import draft_turns, game, rooms
from app.catalog import SLOTS, load_catalog
from app.db import Session, Cup
from test_preflight import clean, client, ready_room
from test_community import group_for, start_cup, fixture_room


@pytest.mark.parametrize('count', [2, 3, 4, 8])
def test_two_picks_each_direction_and_single_final_pick(count):
    state = draft_turns.initial()
    teams = [{} for _ in range(count)]
    current = 0
    actual = []
    while current is not None:
        assert len(teams[current]) < 11
        actual.append((current, state['draftRound'], state['draftDirection'], state['turnPicks']))
        teams[current][str(len(teams[current]))] = True
        current = draft_turns.after_pick(state, teams, current)
        assert len(actual) <= 11 * count
    expected = []
    for round_number in range(1, 7):
        direction = 1 if round_number % 2 else -1
        seats = list(range(count)) if direction == 1 else list(reversed(range(count)))
        for seat in seats:
            for chance in range(1 if round_number == 6 else 2):
                expected.append((seat, round_number, direction, chance))
    assert actual == expected
    assert all(len(team) == 11 for team in teams)


def test_completed_seats_are_skipped_and_legacy_rotation_is_preserved():
    full = {str(index): True for index in range(11)}
    state = {**draft_turns.initial(), 'turnPicks': 1}
    assert draft_turns.after_pick(state, [full, {}, full], 0) == 1
    # The endpoint is full: reverse, then visit the only unfinished seat again.
    state['turnPicks'] = 1
    assert draft_turns.after_pick(state, [full, {}, full], 1) == 1
    assert state['draftDirection'] == -1 and state['draftRound'] == 2
    assert draft_turns.after_pick({}, [{}, {}, {}], 0) == 1
    assert draft_turns.after_pick({}, [{}, {}, {}], 2) == 0
    assert draft_turns.after_pick(state, [full, full, full], 0) is None


def test_room_reconnect_second_chance_stale_actions_and_private_rolls():
    a, b = client(), client('bob')
    room = a.post('/api/rooms', json=dict(format='knockout', capacity=2, competition='ipl', pick_seconds=30)).json()
    b.post('/api/rooms/join', json={'code': room['code']})
    room = ready_room(a, room, b)
    path = f"/api/rooms/{room['id']}"
    room = a.post(path + '/actions', json={'action': 'start', 'version': room['version']}).json()
    for seat, chance, round_number in [(0, 0, 1), (0, 1, 1), (1, 0, 1), (1, 1, 1), (1, 0, 2), (1, 1, 2), (0, 0, 2)]:
        active, waiting = (a, b) if seat == 0 else (b, a)
        room = active.get(path).json()  # A fresh connection must retain the chance.
        assert (room['state']['turn'], room['state']['turnPicks'], room['state']['draftRound']) == (seat, chance, round_number)
        assert waiting.post(path + '/actions', json={'action': 'roll', 'version': room['version']}).status_code == 403
        rolled = active.post(path + '/actions', json={'action': 'roll', 'version': room['version']})
        assert rolled.status_code == 200, rolled.text
        room = rolled.json()
        assert waiting.get(path).json()['state']['rolled'] is None
        player, slots = next(iter(room['state']['rolled']['allowedSlots'].items()))
        payload = dict(action='pick', version=room['version'], draft_revision=room['state']['draftRevision'], player_id=player, slot_id=slots[0])
        picked = active.post(path + '/actions', json=payload)
        assert picked.status_code == 200, picked.text
        assert active.post(path + '/actions', json=payload).status_code == 409
        room = picked.json()
        assert room['state']['rolled'] is None
        assert room['state']['deadline'] == room['serverTime'] + 30
        if room['state']['turn'] == seat:
            # The second chance cannot reuse the first chance's squad.
            no_fresh_roll = active.post(path + '/actions', json=dict(action='pick', version=room['version'], draft_revision=room['state']['draftRevision'], player_id=player, slot_id=slots[0]))
            assert no_fresh_roll.status_code == 409
            assert no_fresh_roll.json()['detail'] == 'Roll a squad before picking a player'


def test_timeout_uses_both_chances_and_ai_takes_the_return_round():
    with Session() as session:
        players = [p for squad in load_catalog(session, 'ipl')['squads'] for p in squad['players']]
    state = rooms.new_state('host', SimpleNamespace(name='Host', capacity=2, format='knockout', pick_seconds=30, competition='ipl'))
    state['members'][0]['ready'] = True
    rooms.start(state, 100)
    for seat, chance in [(0, 0), (0, 1), (1, 0), (1, 1), (1, 0), (1, 1)]:
        assert (state['turn'], state['turnPicks']) == (seat, chance)
        deadline = state['deadline']
        snapshot = copy.deepcopy(state)
        assert not rooms.advance(state, players, deadline - .01)
        assert state == snapshot
        assert rooms.advance(state, players, deadline)
        assert state['lastPick']['automatic']
        next_interval = rooms.AI_PICK_SECONDS if state['members'][state['turn']]['is_ai'] else state['seconds']
        assert state['deadline'] == deadline + next_interval
    assert state['turn'] == 0 and state['draftRound'] == 2
    rooms.advance(state, players, 10000)
    assert state['phase'] == 'complete' and len(state['taken']) == 22
    assert state['champion'] and state['matches'][0]['status'] == 'complete'
    assert all(len(member['xi']) == 11 for member in state['members'])


@pytest.mark.parametrize('rules_version', [1, 2])
def test_practice_complete_draft_delays_and_saved_rules(rules_version):
    with Session() as session:
        squads = load_catalog(session, 't20')['squads']
    state = game.initial(rules_version=rules_version)
    if rules_version == 1:
        for key in draft_turns.initial(): state.pop(key)  # An actual pre-upgrade save.
    order = []
    while state['turn'] != 'done':
        order.append(state['turn'])
        if state['turn'] == 'you':
            game.act(state, 'roll', squads=squads)
            player, slot = next((p, s) for p in state['rolled']['players'] for s in SLOTS if s['id'] not in state['yourXI'] and p['role'] in s['accepts'] and game.fits(state, p))
            game.act(state, 'pick', player['id'], slot['id'], squads=squads)
        else:
            deadline = state['aiDeadline']
            with pytest.raises(HTTPException): game.act(state, 'roll', squads=squads)
            assert not game.advance(state, squads, deadline - .01)
            assert game.advance(state, squads, deadline)
            if state['turn'] == 'opp': assert state['aiDeadline'] == deadline + game.AI_PICK_SECONDS
        state = copy.deepcopy(state)  # Continue from a persisted snapshot.
        assert len(order) <= 22
    if rules_version == 2:
        assert order == ['you']*2 + ['opp']*4 + ['you']*4 + ['opp']*4 + ['you']*4 + ['opp']*3 + ['you']
    else:
        assert order == ['you', 'opp'] * 11
    assert state['pickNumber'] == 23 and 'aiDeadline' not in state
    assert len(state['yourXI']) == len(state['opponentXI']) == 11


@pytest.mark.parametrize('rules_version', [1, 2])
def test_cup_fixtures_and_practice_keep_the_cups_frozen_turn_rules(rules_version):
    a, b = client(), client('bob')
    group = group_for(a, b)
    cup = start_cup(a, group)
    assert cup['rulesVersion'] == 2
    if rules_version == 1:
        with Session.begin() as session:
            row = session.get(Cup, cup['id'])
            row.state = {**row.state, 'rulesVersion': 1}
    room = fixture_room(a, b, group, cup['fixtures'][0])
    assert room['state']['draftRulesVersion'] == rules_version
    practice = a.post('/api/games', json={'preset': cup['preset'], 'draft_rules_version': rules_version})
    assert practice.status_code == 201
    assert practice.json()['state']['draftRulesVersion'] == rules_version
    assert a.post('/api/games', json={'draft_rules_version': 99}).status_code == 422
