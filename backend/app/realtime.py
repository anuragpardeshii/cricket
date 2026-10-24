"""Authenticated room snapshots over WebSocket; media travels through LiveKit."""
import asyncio
from collections import defaultdict
from contextlib import suppress
from datetime import timedelta
import json
import logging
import os
import secrets
import time
from uuid import UUID

import psycopg
import anyio
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import delete

from .db import Session, Room, LoginSession, User, RoomSocketTicket, engine, connect_args, now
from .main import ORIGIN, authenticated, db, digest, limit
from .rooms import project

router = APIRouter(prefix='/api/rooms')
log = logging.getLogger('out.security')


def access(session, room_id, session_hash):
    auth = session.get(LoginSession, session_hash)
    if not auth or auth.expires <= now():
        raise HTTPException(401, 'Sign in required')
    user = session.get(User, auth.user_id)
    if not user or user.is_blocked:
        raise HTTPException(403, 'Account blocked')
    room = session.get(Room, room_id)
    if not room or auth.user_id in room.state.get('removedUsers', []):
        raise HTTPException(403, 'You have left or been removed from this room.')
    member = next((m for m in room.state['members'] if m['uid'] == auth.user_id and not m.get('departed') and not m.get('is_ai')), None)
    if not member:
        raise HTTPException(403, 'Room membership required')
    return auth, room, member


def socket_url(room_id):
    origin = os.getenv('ROOM_WEBSOCKET_ORIGIN', '').rstrip('/')
    if not origin and os.getenv('RENDER_EXTERNAL_HOSTNAME'):
        origin = 'wss://' + os.environ['RENDER_EXTERNAL_HOSTNAME']
    return f'{origin}/api/rooms/{room_id}/live'


@router.post('/{room_id}/connection')
def connection(room_id: UUID, auth=Depends(authenticated), session=Depends(db)):
    from .voice import configured
    access(session, str(room_id), auth.token_hash)
    limit('room-connection:' + auth.user_id, 30)
    ticket = secrets.token_urlsafe(32)
    session.execute(delete(RoomSocketTicket).where(RoomSocketTicket.expires <= now()))
    session.add(RoomSocketTicket(token_hash=digest(ticket), room_id=str(room_id), session_hash=auth.token_hash, expires=now() + timedelta(seconds=30)))
    session.commit()
    return dict(ticket=ticket, url=socket_url(room_id), voiceAvailable=configured())


def consume_ticket(room_id, ticket):
    with Session.begin() as session:
        session_hash = session.scalar(delete(RoomSocketTicket).where(
            RoomSocketTicket.token_hash == digest(ticket), RoomSocketTicket.room_id == room_id,
            RoomSocketTicket.expires > now()).returning(RoomSocketTicket.session_hash))
        if not session_hash:
            raise HTTPException(401, 'Connection ticket expired')
        auth, _, _ = access(session, room_id, session_hash)
        return session_hash, auth.user_id


def snapshot(room_id, session_hash):
    with Session() as session:
        auth, room, _ = access(session, room_id, session_hash)
        return project(room, auth.user_id, time.time())


class RoomSignals:
    def __init__(self):
        self.rooms = defaultdict(set)
        self.users = defaultdict(int)
        self.voice = asyncio.Event()

    def changed(self, room_id):
        groups = self.rooms.values() if room_id == '*' else [self.rooms.get(room_id, ())]
        for group in groups:
            for event in group:
                event.set()
        self.voice.set()


async def listen(signals):
    """One dedicated connection per API worker; reconnect after database restarts."""
    params = engine.url.translate_connect_args(username='user', database='dbname')
    params.update(dict(engine.url.query))
    params.update(connect_args)
    while True:
        try:
            async with await psycopg.AsyncConnection.connect(**params, autocommit=True) as connection:
                await connection.execute('LISTEN out_room_changes')
                signals.changed('*')
                async for notification in connection.notifies():
                    signals.changed(notification.payload)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.error('room_notifications_unavailable')
            await asyncio.sleep(3)


async def receive_message(socket):
    message = await socket.receive_text()
    if len(message) > 2048:
        raise ValueError('Message too large')
    value = json.loads(message)
    if not isinstance(value, dict):
        raise ValueError('Invalid message')
    return value


@router.websocket('/{room_id}/live')
async def room_socket(socket: WebSocket, room_id: UUID):
    # HTTP middleware does not run for WebSockets. Check Origin explicitly.
    if socket.headers.get('origin') != ORIGIN:
        await socket.close(code=4403)
        return
    await socket.accept()
    tasks = []
    signals = socket.app.state.room_signals
    event = asyncio.Event()
    user_id = None
    room_key = str(room_id)
    try:
        message = await asyncio.wait_for(receive_message(socket), timeout=5)
        ticket = message.get('ticket')
        if message.get('type') != 'authenticate' or not isinstance(ticket, str) or len(ticket) != 43:
            raise HTTPException(401, 'Connection ticket required')
        session_hash, identity = await asyncio.to_thread(consume_ticket, room_key, ticket)
        if signals.users[identity] >= 3:
            await socket.close(code=4429)
            return
        user_id = identity
        signals.users[user_id] += 1
        signals.rooms[room_key].add(event)

        async def send_updates():
            previous = None
            heartbeat = 0
            while True:
                event.clear()
                value = await asyncio.to_thread(snapshot, room_key, session_hash)
                # Live commentary advances with time, even when room.version is unchanged.
                fingerprint = json.dumps({k: v for k, v in value.items() if k != 'serverTime'}, sort_keys=True)
                if fingerprint != previous:
                    await asyncio.wait_for(socket.send_json(dict(type='room', room=value)), timeout=10)
                    previous = fingerprint
                    heartbeat = time.monotonic()
                elif time.monotonic() - heartbeat >= 10:
                    await asyncio.wait_for(socket.send_json(dict(type='heartbeat', serverTime=value['serverTime'])), timeout=10)
                    heartbeat = time.monotonic()
                # Recheck permissions and timed projections even when NOTIFY is unavailable.
                with suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(event.wait(), timeout=1)

        async def receive_pings():
            last = 0
            while True:
                value = await asyncio.wait_for(receive_message(socket), timeout=90)
                current = time.monotonic()
                if value != {'type': 'ping'} or current - last < 1:
                    raise ValueError('Invalid heartbeat')
                last = current

        tasks = [asyncio.create_task(send_updates()), asyncio.create_task(receive_pings())]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    except HTTPException as exc:
        with suppress(RuntimeError, WebSocketDisconnect):
            await socket.close(code=4401 if exc.status_code == 401 else 4403)
    except (ValueError, asyncio.TimeoutError):
        with suppress(RuntimeError, WebSocketDisconnect):
            await socket.close(code=1008)
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        raise
    except Exception:
        log.error('room_socket_failed')
        with suppress(RuntimeError, WebSocketDisconnect):
            await socket.close(code=1011)
    finally:
        # Finish child-task cleanup even if the ASGI server cancels this scope.
        with anyio.CancelScope(shield=True):
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            signals.rooms[room_key].discard(event)
            if not signals.rooms[room_key]:
                del signals.rooms[room_key]
            if user_id:
                signals.users[user_id] -= 1
                if not signals.users[user_id]:
                    del signals.users[user_id]
