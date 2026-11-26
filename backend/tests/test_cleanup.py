from datetime import timedelta

from sqlalchemy import select

from app.cleanup import cleanup
from app.db import (Session, User, Room, Game, LoginSession, RoomSocketTicket,
                    VoiceGrant, MatchArchive, MatchPlayer, Achievement, RateBucket, now)
from test_preflight import clean, client


def test_retention_boundary_cascades_and_preserves_accounts_and_results():
    client()
    timestamp = now()
    cutoff = timestamp - timedelta(hours=12)
    with Session.begin() as session:
        user = session.scalar(select(User))
        user_id = user.id
        auth = session.scalar(select(LoginSession))
        for key, created in [('old', cutoff), ('recent', cutoff + timedelta(seconds=1))]:
            session.add(Room(id=key, owner_id=user_id, code='AAAA' if key == 'old' else 'BBBB', created_at=created,
                             state={'chat': [{'text': 'private conversation'}]}))
            session.add(Game(id=key, owner_id=user_id, code=key,
                             created_at=created - timedelta(hours=12), state={}))
        session.flush()
        session.add(RoomSocketTicket(token_hash='ticket', room_id='old',
                                     session_hash=auth.token_hash, expires=timestamp + timedelta(minutes=1)))
        session.add(VoiceGrant(member_id='member', room_id='old', user_id=user_id,
                               session_hash=auth.token_hash))
        session.add(MatchArchive(id='result', data={}, created_at=cutoff))
        session.flush()
        session.add(MatchPlayer(match_id='result', user_id=user_id, won=True))
        session.add(Achievement(user_id=user_id, code='first-win', source='result'))
        session.add(RateBucket(key='expired', count=1, expires=timestamp - timedelta(seconds=1)))
    assert cleanup(timestamp=timestamp) == {'rooms': 1, 'games': 1}
    with Session() as session:
        assert session.get(Room, 'old') is None
        assert session.get(Game, 'old') is None
        assert session.get(RoomSocketTicket, 'ticket') is None
        assert session.get(VoiceGrant, 'member') is None
        assert session.get(RateBucket, 'expired') is None
        assert session.get(Room, 'recent').state['chat']
        assert session.get(Game, 'recent')
        assert session.get(User, user_id)
        assert session.get(MatchArchive, 'result')
        assert session.get(MatchPlayer, ('result', user_id))
        assert session.get(Achievement, (user_id, 'first-win'))
    assert cleanup(timestamp=timestamp) == {'rooms': 0, 'games': 0}
    assert cleanup(all_rooms=True, timestamp=timestamp) == {'rooms': 1, 'games': 0}


def test_expired_guest_cleanup_after_room_retention():
    timestamp = now()
    with Session.begin() as session:
        session.add(User(id='guest', username='guest', email='guest@example.com',
                         password_hash='unused', is_guest=True))
        session.flush()
        session.add(Room(id='room', owner_id='guest', code='ABCD', state={},
                         created_at=timestamp - timedelta(days=2)))
        session.add(LoginSession(token_hash='expired', user_id='guest', csrf='csrf',
                                 expires=timestamp - timedelta(seconds=1)))
    cleanup(timestamp=timestamp)
    with Session() as session:
        assert session.get(User, 'guest') is None


def test_scheduler_runs_immediately_and_retries_after_failure(monkeypatch):
    import asyncio
    from app import cleanup as module
    calls = []

    def fail_once():
        calls.append('cleanup')
        if calls.count('cleanup') == 1:
            raise RuntimeError('temporary failure')

    async def sleep(seconds):
        assert seconds == 300
        if calls.count('cleanup') == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(module, 'cleanup', fail_once)
    monkeypatch.setattr(asyncio, 'sleep', sleep)

    async def run():
        try:
            await module.maintain()
        except asyncio.CancelledError:
            pass

    asyncio.run(run())
    assert calls == ['cleanup', 'cleanup']
