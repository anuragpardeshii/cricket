"""Real PostgreSQL and WebSocket tests; LiveKit control API is mocked separately."""
import asyncio
import copy
import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
import time

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app, COOKIE, digest
from app import rooms, voice
from app.catalog import load_catalog
from app.db import Session, Room, RoomSocketTicket, VoiceGrant, now
from app.realtime import consume_ticket, RoomSignals, listen
from test_preflight import clean, client, room_for, HEADERS


def ticket(client, room):
    response = client.post(f"/api/rooms/{room['id']}/connection", json={})
    assert response.status_code == 200, response.text
    return response.json()['ticket']


def authenticate(socket, value):
    socket.send_json({'type': 'authenticate', 'ticket': value})
    message = socket.receive_json()
    assert message['type'] == 'room'
    return message['room']


def test_connection_requires_membership_origin_csrf_and_single_use():
    a = client(); outsider = client('outsider'); room = room_for(a)
    path = f"/api/rooms/{room['id']}/connection"
    assert outsider.post(path, json={}).status_code == 403
    assert a.post(path, json={}, headers={'origin': 'https://evil.example'}).status_code == 403
    assert a.post(path, json={}, headers={'x-csrf-token': 'wrong'}).status_code == 403
    value = ticket(a, room)
    with Session() as session:
        row = session.get(RoomSocketTicket, digest(value))
        assert row and row.session_hash == digest(a.cookies.get(COOKIE))
        assert row.expires <= now() + timedelta(seconds=30)
    consume_ticket(room['id'], value)
    with pytest.raises(HTTPException) as exc:
        consume_ticket(room['id'], value)
    assert exc.value.status_code == 401


def test_expired_wrong_room_and_revoked_tickets():
    a = client(); first = room_for(a); second = room_for(a)
    value = ticket(a, first)
    with pytest.raises(HTTPException): consume_ticket(second['id'], value)
    consume_ticket(first['id'], value)
    value = ticket(a, first)
    with Session.begin() as session:
        session.get(RoomSocketTicket, digest(value)).expires = now() - timedelta(seconds=1)
    with pytest.raises(HTTPException): consume_ticket(first['id'], value)
    value = ticket(a, first)
    assert a.post('/api/auth/logout', json={}).status_code == 200
    with pytest.raises(HTTPException): consume_ticket(first['id'], value)


def test_socket_rejects_other_origins_and_invalid_tickets():
    with client() as a:
        room = room_for(a)
        path = f"/api/rooms/{room['id']}/live"
        with pytest.raises(WebSocketDisconnect) as exc:
            with a.websocket_connect(path, headers={'origin': 'https://evil.example'}): pass
        assert exc.value.code == 4403
        with a.websocket_connect(path) as socket:
            socket.send_json({'type': 'authenticate', 'ticket': 'x' * 43})
            with pytest.raises(WebSocketDisconnect) as exc: socket.receive_json()
            assert exc.value.code == 4401


def test_socket_pushes_join_rename_and_reconnect_snapshot():
    with client() as a:
        room = room_for(a); b = client('bob')
        path = f"/api/rooms/{room['id']}/live"
        with a.websocket_connect(path) as socket:
            initial = authenticate(socket, ticket(a, room))
            assert initial['you'] == room['you']
            assert all('uid' not in person for person in initial['state']['members'])
            joined = b.post('/api/rooms/join', json={'code': room['code']})
            assert joined.status_code == 200
            update = socket.receive_json()['room']
            assert len(update['state']['members']) == 2
            assert update['you'] == room['you']  # Viewer-specific projection, not Bob's response.
            assert b.post(f"/api/rooms/{room['id']}/name", json={'name': 'New Bob'}).status_code == 200
            assert socket.receive_json()['room']['state']['members'][1]['name'] == 'New Bob'
        with a.websocket_connect(path) as socket:
            latest = authenticate(socket, ticket(a, room))
            assert latest['version'] > initial['version']
            assert latest['state']['members'][1]['name'] == 'New Bob'


@pytest.mark.parametrize('reason', ['logout', 'exit', 'kick'])
def test_active_socket_loses_access(reason):
    with client() as a:
        room = room_for(a, capacity=2); b = client('bob')
        joined = b.post('/api/rooms/join', json={'code': room['code']}).json()
        with b.websocket_connect(f"/api/rooms/{room['id']}/live") as socket:
            authenticate(socket, ticket(b, room))
            if reason == 'logout':
                response = b.post('/api/auth/logout', json={})
            elif reason == 'exit':
                response = b.post(f"/api/rooms/{room['id']}/exit", json={})
            else:
                response = a.post(f"/api/rooms/{room['id']}/kick-vote", json={'target_id': joined['you']})
            assert response.status_code == 200
            with pytest.raises(WebSocketDisconnect) as exc:
                while True: socket.receive_json()
            assert exc.value.code == (4401 if reason == 'logout' else 4403)


def test_socket_reveals_timed_overs_without_version_change():
    with client() as a:
        room = room_for(a, capacity=2)
        with Session.begin() as session:
            row = session.get(Room, room['id']); state = copy.deepcopy(row.state)
            players = [p for squad in load_catalog(session)['squads'] for p in squad['players']]
            started = time.time()
            state['members'][0]['ready']=True
            rooms.start(state, started)
            rooms.advance(state, players, started + 10000)
            state['phase'] = 'live'; state['champion'] = None; state.pop('award', None)
            for match in state['matches']:
                match['status'] = 'live'; match['startedAt'] = time.time(); match['endsAt'] = time.time() + 1000
            row.state = state
        with a.websocket_connect(f"/api/rooms/{room['id']}/live") as socket:
            first = authenticate(socket, ticket(a, room))
            updated = socket.receive_json()['room']
            assert updated['version'] == first['version']
            assert len(updated['state']['matches'][0]['timeline']) > len(first['state']['matches'][0]['timeline'])
            for match in updated['state']['matches']:
                assert not {'plan', 'winner', 'result'}.intersection(match)


@pytest.fixture
def livekit_config(monkeypatch):
    monkeypatch.setenv('LIVEKIT_URL', 'wss://test.livekit.cloud')
    monkeypatch.setenv('LIVEKIT_API_KEY', 'test-key')
    monkeypatch.setenv('LIVEKIT_API_SECRET', 'test-only-secret-with-at-least-32-characters')
    return 'test-only-secret-with-at-least-32-characters'


def test_voice_token_is_short_lived_room_scoped_and_microphone_only(livekit_config):
    a = client(); room = room_for(a); outsider = client('outsider')
    path = f"/api/rooms/{room['id']}/voice"
    assert outsider.post(path, json={}).status_code == 404
    response = a.post(path, json={})
    assert response.status_code == 200
    payload = jwt.decode(response.json()['token'], livekit_config, algorithms=['HS256'])
    assert payload['sub'] != room['you']
    assert json.loads(payload['metadata']) == {'memberId': room['you']}
    assert payload['exp'] - payload['nbf'] == 120
    grants = payload['video']
    assert grants['room'] == voice.PREFIX + room['id']
    assert grants['roomJoin'] and grants['canSubscribe']
    assert grants['canPublishSources'] == ['microphone']
    assert grants['canPublishData'] is False and not grants.get('roomAdmin')
    assert not grants.get('canUpdateOwnMetadata')
    with Session() as session:
        assert session.get(VoiceGrant, room['you']).session_hash == digest(a.cookies.get(COOKIE))
    assert a.post(f"/api/rooms/{room['id']}/exit", json={}).status_code == 200
    assert a.post(path, json={}).status_code == 403


def test_missing_voice_config_does_not_block_room_connection(monkeypatch):
    monkeypatch.delenv('LIVEKIT_API_SECRET', raising=False)
    a = client(); room = room_for(a)
    assert a.post(f"/api/rooms/{room['id']}/connection", json={}).json()['voiceAvailable'] is False
    assert a.post(f"/api/rooms/{room['id']}/voice", json={}).status_code == 503


def test_media_server_removes_exited_and_logged_out_members(livekit_config):
    a = client(); b = client('bob'); room = room_for(a)
    bob = b.post('/api/rooms/join', json={'code': room['code']}).json()
    for participant in [a, b]:
        assert participant.post(f"/api/rooms/{room['id']}/voice", json={}).status_code == 200
    with Session() as session:
        alice_id = session.get(VoiceGrant, room['you']).identity
        bob_id = session.get(VoiceGrant, bob['you']).identity
    remote = SimpleNamespace(room=SimpleNamespace(
        list_rooms=AsyncMock(return_value=SimpleNamespace(rooms=[SimpleNamespace(name=voice.PREFIX + room['id'])])),
        list_participants=AsyncMock(return_value=SimpleNamespace(participants=[SimpleNamespace(identity=alice_id), SimpleNamespace(identity=bob_id)])),
        remove_participant=AsyncMock()))
    asyncio.run(voice.reconcile(remote))
    remote.room.remove_participant.assert_not_called()
    assert b.post(f"/api/rooms/{room['id']}/exit", json={}).status_code == 200
    asyncio.run(voice.reconcile(remote))
    request = remote.room.remove_participant.call_args.args[0]
    assert request.identity == bob_id and request.revoke_token_ts >= int(time.time())
    remote.room.remove_participant.reset_mock()
    assert a.post('/api/auth/logout', json={}).status_code == 200
    asyncio.run(voice.reconcile(remote))
    assert {call.args[0].identity for call in remote.room.remove_participant.call_args_list} == {alice_id, bob_id}


def test_new_login_cannot_make_an_old_voice_token_valid_again(livekit_config):
    a = client(); room = room_for(a); path = f"/api/rooms/{room['id']}/voice"
    old = jwt.decode(a.post(path, json={}).json()['token'], livekit_config, algorithms=['HS256'])['sub']
    login = a.post('/api/auth/login', json={'email': 'alice@example.com', 'password': 'a distinct long passphrase alice'})
    a.headers['x-csrf-token'] = login.json()['csrf']
    new = jwt.decode(a.post(path, json={}).json()['token'], livekit_config, algorithms=['HS256'])['sub']
    assert new != old
    assert voice.authorized_identities(room['id'], [old, new]) == {new}


def test_committed_database_change_wakes_room_listener():
    a = client(); room = room_for(a)

    async def check():
        signals = RoomSignals(); event = asyncio.Event()
        signals.rooms[room['id']].add(event)
        task = asyncio.create_task(listen(signals))
        try:
            await asyncio.wait_for(event.wait(), 5)  # Listener is subscribed.
            event.clear()
            def update():
                with Session.begin() as session:
                    session.get(Room, room['id']).version += 1
            await asyncio.to_thread(update)
            await asyncio.wait_for(event.wait(), 2)
        finally:
            task.cancel(); await asyncio.gather(task, return_exceptions=True)

    asyncio.run(check())
