from types import SimpleNamespace

import pytest

from app import game, rooms
from app.catalog import load_catalog
from app.db import Session
from app.draft_pool import person_key, EDITION_DETAILS
from test_preflight import clean, client

POOLS=[(competition,e['year'],e['teams']) for competition,editions in EDITION_DETAILS.items() for e in editions]


@pytest.mark.parametrize('competition,edition,count',POOLS)
def test_every_edition_completes_eight_unique_xis(competition,edition,count,monkeypatch):
    with Session() as session: catalog=load_catalog(session,competition,edition)
    players=[p for s in catalog['squads'] for p in s['players']]
    pool=[p for p in players if p['competition']==competition and p['edition']==edition]
    assert len({p['squad'] for p in pool})==count
    assert len(pool)>=count*14
    state=rooms.new_state('host',SimpleNamespace(name='Host',format='knockout',capacity=8,pick_seconds=30,competition=competition,edition=edition))
    state['members'][0]['ready']=True; rooms.start(state,100)
    monkeypatch.setattr(rooms,'fixtures',lambda *_:None)
    for turn in range(88):
        rooms.roll(state,players,ts=100+turn)
        assert all(p['competition']==competition and p['edition']==edition for p in state['rolled']['players'])
        rooms.pick(state,players,100+turn,automatic=True)
    picked=[p for m in state['members'] for p in m['xi'].values()]
    assert len(picked)==len({person_key(p) for p in picked})==88
    assert all(p['competition']==competition and p['edition']==edition for p in picked)
    assert state['phase']=='live'
    # Practice human rolls and the delayed AI both respect the same edition.
    practice=game.initial(competition,edition)
    game.act(practice,'roll',squads=catalog['squads'])
    assert all(p['edition']==edition and p['competition']==competition for p in practice['rolled']['players'])
    player=practice['rolled']['players'][0]
    slot=next(s['id'] for s in catalog['slots'] if player['role'] in s['accepts'])
    game.act(practice,'pick',player['id'],slot,squads=catalog['squads'])
    game.advance(practice,catalog['squads'],practice['aiDeadline'])
    assert all(p['edition']==edition and p['competition']==competition for p in practice['opponentXI'].values())


def test_edition_api_filtering_and_game_modes():
    c=client()
    assert c.get('/api/catalog?competition=t20&edition=2024').status_code==200
    squads=c.get('/api/catalog?competition=t20&edition=2024').json()['squads']
    assert len(squads)==20
    assert {'UGANDA','UNITED STATES','CANADA','OMAN','NEPAL','PAPUA NEW GUINEA'}<={s['country'] for s in squads}
    for squad in squads:
        assert len(squad['players'])>=15
        assert len({person_key(p) for p in squad['players']})==len(squad['players'])
    assert len(c.get('/api/catalog?competition=ipl&edition=2023').json()['squads'])==10
    assert len(c.get('/api/catalog?competition=odi').json()['squads'])==113
    assert c.get('/api/catalog?competition=odi&edition=2024').status_code==422
    assert c.get('/api/catalog?edition=2023').status_code==422
    settings=dict(competition='ipl',edition=2023)
    practice=c.post('/api/games',json=settings).json()
    practice_state=c.get('/api/games/'+practice['id']).json()['state']
    assert practice_state['competition']=='t20' and practice_state['edition'] is None
    room_settings=dict(format='knockout',capacity=8,pick_seconds=30,visibility='public',**settings)
    room=c.post('/api/rooms',json=room_settings).json()
    room_state=c.get('/api/rooms/'+room['id']).json()['state']
    assert room_state['competition']=='ipl' and room_state['edition'] is None
    assert next(r for r in c.get('/api/rooms/public').json()['rooms'] if r['code']==room['code'])['edition'] is None
    for invalid in [dict(competition='ipl',edition=2007),dict(competition='odi',edition=2024),dict(competition='t20',edition=2050)]:
        assert c.post('/api/games',json=invalid).json()['state']['competition']=='t20'
        assert c.post('/api/rooms',json={**room_settings,**invalid}).json()['state']['edition'] is None


def test_historical_squad_boundaries_and_namesakes():
    with Session() as session: squads=load_catalog(session)['squads']
    def roster(country,tournament): return next(s['players'] for s in squads if s['country']==country and s['tournament']==tournament)
    assert len(roster('ENGLAND','WORLD CUP 2019'))==15
    assert len(roster('CHENNAI SUPER KINGS','IPL 2023'))==25
    assert len(roster('KOLKATA KNIGHT RIDERS','IPL 2023'))==22
    dutch={p['name'] for p in roster('NETHERLANDS','T20 WORLD CUP 2024')}
    assert {'Kyle Klein','S Zulfiqar'}<=dutch
    assert not {'R Klein','Fred Klaassen','Daniel Doram'}&dutch
    players=[p for s in squads for p in s['players']]
    keys=lambda name:{person_key(p) for p in players if p['name']==name}
    assert keys('Ali Khan').isdisjoint(keys('A Khan'))
    assert keys('Karan Sharma').isdisjoint(keys('K Sharma'))
    assert keys('Kuldip Yadav').isdisjoint(keys('K Yadav'))
    assert keys('Shoaib Malik').isdisjoint(keys('S Malik'))
    assert len(keys('C Anderson'))==1


def test_archive_covers_every_edition_and_historical_franchise():
    from app.draft_pool import EDITIONS
    assert EDITIONS['ipl']==tuple(range(2026,2007,-1))
    assert EDITIONS['t20']==(2026,2024,2022,2021,2016,2014,2012,2010,2009,2007)
    assert EDITIONS['odi']==(2023,2019,2015,2011,2007,2003,1999,1996,1992)
    with Session() as session:
        def teams(comp,year):return {s['country'] for s in load_catalog(session,comp,year)['squads']}
        assert {'DECCAN CHARGERS','DELHI DAREDEVILS','KINGS XI PUNJAB'}<=teams('ipl',2008)
        assert {'KOCHI TUSKERS KERALA','PUNE WARRIORS INDIA'}<=teams('ipl',2011)
        assert {'GUJARAT LIONS','RISING PUNE SUPERGIANTS'}<=teams('ipl',2016)
        assert not {'CHENNAI SUPER KINGS','RAJASTHAN ROYALS'}&teams('ipl',2016)
        assert 'RISING PUNE SUPERGIANT' in teams('ipl',2017)
        assert {'ITALY','SCOTLAND'}<=teams('t20',2026)
        assert 'BANGLADESH' not in teams('t20',2026)
        assert {'KENYA','NETHERLANDS','UNITED ARAB EMIRATES'}<=teams('odi',1996)
        assert 'BERMUDA' in teams('odi',2007)
        for comp,year,count in POOLS:
            squads=load_catalog(session,comp,year)['squads']
            assert len(squads)==count
            for squad in squads:
                assert len(squad['players'])>=14,(comp,year,squad['country'])
                assert len({person_key(p) for p in squad['players']})==len(squad['players'])


def test_full_names_abbreviations_and_saved_cards_share_identity():
    with Session() as session:players=[p for s in load_catalog(session)['squads'] for p in s['players']]
    def ids(*names):return {person_key(p) for p in players if p['name'] in names}
    for names in [('V Kohli','Virat Kohli'),('R Sharma','Rohit Sharma'),
                  ('A Sohail','Aamir Sohail','Aamer Sohail'),('MS Dhoni','Mahendra Singh Dhoni'),
                  ('V Chakaravarthy','Varun Chakaravarthy','Varun Chakravarthy')]:
        assert len(ids(*names))==1,names
    assert ids('S Patil').isdisjoint(ids('Swapnil Patil'))
    assert ids('Harmeet Singh Bansal').isdisjoint(ids('Harmeet Singh Baddhan'))
    old=next(p for p in players if p['name']=='V Kohli')
    saved=dict(old,personId='vkohli')
    assert person_key(saved)==person_key(old)
    current={}
    from app.catalog import SLOTS
    from app.draft_pool import eligible_picks
    options=eligible_picks([{'n3':saved},current],current,players,SLOTS)
    assert not any(person_key(o['player'])==person_key(old) for o in options)


def test_identical_names_and_players_who_changed_countries():
    with Session() as session:squads=load_catalog(session)['squads']
    def person(country,tournament,name):
        squad=next(s for s in squads if s['country']==country and s['tournament']==tournament)
        return person_key(next(p for p in squad['players'] if p['name']==name))
    american=person('UNITED STATES','T20 WORLD CUP 2024','Harmeet Singh')
    assert person('RAJASTHAN ROYALS','IPL 2013','Harmeet Singh')==american
    assert person('DECCAN CHARGERS','IPL 2010','Harmeet Singh Bansal')!=american
    assert person('KINGS XI PUNJAB','IPL 2015','Shivam Sharma')!=person('CANADA','T20 WORLD CUP 2026','Shivam Sharma')
    canadian=person('CANADA','T20 WORLD CUP 2026','Jaskarandeep Singh')
    assert person('DECCAN CHARGERS','IPL 2010','Jaskaran Singh')==canadian
    assert person('RISING PUNE SUPERGIANTS','IPL 2016','Jaskaran Singh')!=canadian
    assert person('DELHI DAREDEVILS','IPL 2010','Amit Mishra')!=person('RAJASTHAN ROYALS','IPL 2014','Amit Mishra')
