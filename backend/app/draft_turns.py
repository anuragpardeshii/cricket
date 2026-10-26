"""Persisted turn rules shared by multiplayer and practice drafts."""

RULES_VERSION = 2
PICKS_PER_TURN = 2
XI_SIZE = 11


def initial(rules_version=RULES_VERSION):
    return dict(draftRulesVersion=rules_version, draftRound=1, draftDirection=1, turnPicks=0)


def after_pick(state, teams, current):
    """Return the next seat, or None once every XI is full.

    A snake repeats the endpoint seat on the next round: A, B, C, C, B, A.
    Every visit has two picks, capped by the team's remaining XI positions.
    States saved before these rules retain their original one-pick rotation.
    """
    if all(len(team) >= XI_SIZE for team in teams):
        return None
    if state.get('draftRulesVersion', 1) < RULES_VERSION:
        for offset in range(1, len(teams) + 1):
            seat = (current + offset) % len(teams)
            if len(teams[seat]) < XI_SIZE:
                return seat

    state['turnPicks'] = state.get('turnPicks', 0) + 1
    if state['turnPicks'] < PICKS_PER_TURN and len(teams[current]) < XI_SIZE:
        return current
    state['turnPicks'] = 0
    direction = state.get('draftDirection', 1)
    while True:
        candidate = current + direction
        if candidate < 0 or candidate >= len(teams):
            direction *= -1
            state['draftDirection'] = direction
            state['draftRound'] = state.get('draftRound', 1) + 1
        else:
            current = candidate
        if len(teams[current]) < XI_SIZE:
            return current
