"""Competition boundaries and cricketer identity, independent of card editions."""
import json
import re
from pathlib import Path

EDITION_DETAILS = json.loads(Path(__file__).with_name('catalog-editions.json').read_text())
EDITIONS = {competition: tuple(e['year'] for e in editions) for competition, editions in EDITION_DETAILS.items()}
PLAYER_IDENTITIES = json.loads(Path(__file__).with_name('player-identities.json').read_text())


def validate_edition(selected, edition):
    if edition is not None and edition not in EDITIONS.get(selected, ()):
        raise ValueError('Choose an available edition for this competition')


def competition(tournament):
    return 'ipl' if tournament.startswith('IPL') else 't20' if tournament.startswith('T20') else 'odi'


def squads_for(squads, selected, edition=None):
    # Saved games from before competition selection retain their original pool.
    return [s for s in squads if (not selected or competition(s['tournament']) == selected)
            and (edition is None or int(s['tournament'][-4:]) == edition)]


def person_key(player):
    # Card IDs remain stable across upgrades. Resolve them before saved metadata,
    # which may still contain an abbreviated name from an older catalog.
    if player.get('id') in PLAYER_IDENTITIES:
        return PLAYER_IDENTITIES[player['id']]
    if player.get('personId'):
        return player['personId']
    name = player['name']
    squad = player.get('squad', '')
    # These abbreviated names belong to different people in the historical data.
    if name == 'I Ahmed' and squad == 'PAKISTAN 1992': name = 'Ijaz Ahmed'
    if name == 'M Khan' and squad == 'PAKISTAN 1992': name = 'Moin Khan'
    if name == 'A Khan': name = 'Azam Khan' if player['role'] == 'WK' else 'Avesh Khan'
    return re.sub(r'[^a-z0-9]', '', name.lower())


def used_people(teams):
    return {person_key(p) for xi in teams for p in xi.values()}


def eligible_picks(teams, current, players, slots, taken=()):
    """Reserve enough unique people for every remaining slot across the room.

    Hall's matching condition over five slot groups handles players whose role
    differs across editions. There are only 31 group subsets, regardless of pool
    size; reserve capacities are computed once per request.
    """
    used = used_people(teams); taken = set(taken)
    available = [p for p in players if p['id'] not in taken and person_key(p) not in used]
    role_masks = {'OP': 3, 'BAT': 2, 'AR': 4, 'WK': 8, 'PACE': 16, 'SPIN': 16}
    slot_masks = {'op1': 1, 'op2': 1, 'n3': 2, 'n4': 2, 'n5': 2, 'ar': 4, 'wk': 8,
                  'b1': 16, 'b2': 16, 'b3': 16, 'b4': 16}
    people = {}
    for p in available:
        key = person_key(p)
        people[key] = people.get(key, 0) | role_masks[p['role']]
    missing = [slot_masks[s['id']] for xi in teams for s in slots if s['id'] not in xi]
    reserves = [(mask, sum(bool(roles & mask) for roles in people.values()) -
                 sum(bool(slot & mask) for slot in missing)) for mask in range(1, 32)]
    output = []
    for p in available:
        mask = people[person_key(p)]
        for slot in slots:
            if slot['id'] in current or p['role'] not in slot['accepts']: continue
            if all(slack - bool(mask & subset) + bool(slot_masks[slot['id']] & subset) >= 0
                   for subset, slack in reserves):
                output.append(dict(player=p, slot=slot['id']))
    return output
