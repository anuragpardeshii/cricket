"""Room-scoped LiveKit access and server-enforced removal of revoked members."""
import asyncio
from contextlib import suppress
from datetime import timedelta
import logging
import json
import os
import time
from uuid import UUID

import aiohttp
from fastapi import APIRouter, Depends, HTTPException
from livekit import api

from sqlalchemy import select
from .db import Session, VoiceGrant, uid
from .main import authenticated, db, limit
from .realtime import access
from .room_routes import locked

router = APIRouter(prefix='/api/rooms')
log = logging.getLogger('out.security')
PREFIX = 'out-cricket-'


def configured():
    return all(os.getenv(key) for key in ('LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET'))


@router.post('/{room_id}/voice')
def join_voice(room_id: UUID, auth=Depends(authenticated), session=Depends(db)):
    room = locked(session, room_id, auth.user_id)
    _, _, member = access(session, str(room_id), auth.token_hash)
    if room.state['phase'] == 'expired':
        raise HTTPException(409, 'This room has expired')
    if not configured():
        raise HTTPException(503, 'Voice chat is currently unavailable. You can keep playing.')
    limit('voice-join:' + auth.user_id, 15)
    grant = session.get(VoiceGrant, member['id'])
    if not grant:
        grant = VoiceGrant(member_id=member['id'], identity=uid(), room_id=room.id, user_id=auth.user_id, session_hash=auth.token_hash)
        session.add(grant)
    elif grant.session_hash != auth.token_hash:
        grant.session_hash = auth.token_hash
        grant.identity = uid()
    token = (api.AccessToken(os.environ['LIVEKIT_API_KEY'], os.environ['LIVEKIT_API_SECRET'])
        .with_identity(grant.identity)
        .with_name(member['name'])
        .with_metadata(json.dumps({'memberId': member['id']}))
        .with_ttl(timedelta(minutes=2))
        .with_grants(api.VideoGrants(room_join=True, room=PREFIX + room.id,
            can_publish=True, can_subscribe=True, can_publish_data=False,
            can_publish_sources=['microphone'], can_update_own_metadata=False))
        .to_jwt())
    session.commit()
    return dict(url=os.getenv('LIVEKIT_PUBLIC_URL') or os.environ['LIVEKIT_URL'], token=token)


def authorized_identities(room_id, identities):
    valid = set()
    with Session() as session:
        for identity in identities:
            grant = session.scalar(select(VoiceGrant).where(VoiceGrant.identity == identity))
            if not grant or grant.room_id != room_id:
                continue
            try:
                auth, room, member = access(session, room_id, grant.session_hash)
                if member['id'] == grant.member_id and grant.user_id == auth.user_id and room.state['phase'] != 'expired':
                    valid.add(identity)
            except HTTPException:
                pass
    return valid


async def reconcile(client):
    """Check actual media connections, including reconnects with refreshed tokens.

    This also works after an API restart and with self-hosted LiveKit, where removing
    a participant alone does not revoke their existing JWT.
    """
    rooms = await client.room.list_rooms(api.ListRoomsRequest())
    for room in rooms.rooms:
        if not room.name.startswith(PREFIX):
            continue
        room_id = room.name[len(PREFIX):]
        try:
            UUID(room_id)
        except ValueError:
            continue
        participants = await client.room.list_participants(api.ListParticipantsRequest(room=room.name))
        identities = [p.identity for p in participants.participants]
        if not identities:
            continue
        allowed = await asyncio.to_thread(authorized_identities, room_id, identities)
        for identity in set(identities) - allowed:
            try:
                await client.room.remove_participant(api.RoomParticipantIdentity(
                    room=room.name, identity=identity, revoke_token_ts=int(time.time()) + 1))
            except api.TwirpError as exc:
                if exc.code != 'not_found':
                    raise


async def monitor(signals):
    if not configured():
        return
    async with api.LiveKitAPI(url=os.environ['LIVEKIT_URL'],
        api_key=os.environ['LIVEKIT_API_KEY'], api_secret=os.environ['LIVEKIT_API_SECRET'],
        timeout=aiohttp.ClientTimeout(total=5)) as client:
        while True:
            signals.voice.clear()
            try:
                await reconcile(client)
            except asyncio.CancelledError:
                raise
            except Exception:
                # Never log SDK exception strings: they can contain credentials.
                log.error('voice_access_check_failed')
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(signals.voice.wait(), timeout=5)
            # Coalesce rapid draft writes, keeping control API traffic bounded.
            await asyncio.sleep(0.25)
