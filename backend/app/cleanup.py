"""Retention cleanup, shared by the API scheduler and the operator command."""
import argparse
import logging
from datetime import timedelta

from sqlalchemy import delete, select, func
from .db import Session, LoginSession, RateBucket, RoomSocketTicket, User, Game, Room, now


def cleanup(*, all_rooms=False, timestamp=None):
    timestamp = timestamp or now()
    room_cutoff = timestamp - timedelta(hours=12)
    game_cutoff = timestamp - timedelta(days=1)
    with Session.begin() as session:
        # Chats and simulation timelines live in Room.state and go with the room.
        # Socket tickets and voice grants are removed by ON DELETE CASCADE.
        rooms = delete(Room)
        if not all_rooms:
            rooms = rooms.where(Room.created_at <= room_cutoff)
        room_count = session.execute(rooms).rowcount
        game_count = session.execute(delete(Game).where(Game.created_at <= game_cutoff)).rowcount
        session.execute(delete(LoginSession).where(LoginSession.expires < timestamp))
        session.execute(delete(RateBucket).where(RateBucket.expires < timestamp))
        session.execute(delete(RoomSocketTicket).where(RoomSocketTicket.expires < timestamp))
        # Guest data outlives its cookie only until the next scheduled cleanup.
        guests = session.scalars(select(User.id).where(
            User.is_guest.is_(True),
            ~select(Room.id).where(Room.owner_id == User.id).exists(),
            ~select(Room.id).where(Room.state['members'].contains(func.jsonb_build_array(func.jsonb_build_object('userId',User.id)))).exists(),
            ~select(Room.id).where(Room.state['members'].contains(func.jsonb_build_array(func.jsonb_build_object('uid',User.id)))).exists(),
            ~select(LoginSession.user_id).where(LoginSession.user_id == User.id).exists()
        ).with_for_update(skip_locked=True)).all()
        if guests:
            session.execute(delete(Game).where(Game.owner_id.in_(guests)))
            session.execute(delete(User).where(User.id.in_(guests)))
    return {'rooms': room_count, 'games': game_count}


async def maintain():
    import asyncio
    while True:
        try:
            await asyncio.to_thread(cleanup)
        except Exception:
            # SQL errors can contain credentials or saved room state.
            logging.getLogger('out.security').error('retention_cleanup_failed')
        await asyncio.sleep(300)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all-rooms', action='store_true',
                        help='Immediately delete every room, including active rooms and chats.')
    args = parser.parse_args()
    print(cleanup(all_rooms=args.all_rooms))
