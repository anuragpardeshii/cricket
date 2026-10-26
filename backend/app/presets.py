"""Frozen draft rules used by both practice and friend cups."""
from fastapi import HTTPException
from .draft_pool import eligible_picks

PRESETS = {
    'open-ipl': dict(name='Open IPL', competition='ipl', maxRating=100, description='Every IPL edition. Build your dream XI.'),
    'under-85': dict(name='IPL Under 85', competition='ipl', maxRating=84, description='Only cards rated below 85. Find an unexpected winning XI.'),
}

def rules(preset):
    if preset not in PRESETS: raise HTTPException(422, 'Choose an available draft preset')
    return PRESETS[preset]

def filter_players(players, preset):
    if not preset: return players
    rule = rules(preset)
    return [p for p in players if p.get('competition') == rule['competition'] and p['rating'] <= rule['maxRating']]

def filter_squads(squads, preset):
    if not preset: return squads
    return [{**s, 'players': players} for s in squads if (players := filter_players(s['players'], preset))]

def validate_pool(session, preset, capacity):
    from .catalog import load_catalog, SLOTS
    rule = rules(preset)
    players = filter_players([p for s in load_catalog(session, rule['competition'])['squads'] for p in s['players']], preset)
    teams = [{} for _ in range(capacity)]
    if not eligible_picks(teams, teams[0], players, SLOTS):
        raise HTTPException(409, 'This preset does not have enough distinct players for every XI')
