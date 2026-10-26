from sqlalchemy import delete, select, func
from .db import Session, LoginSession, RateBucket, RoomSocketTicket, User, Game, Room, now
with Session.begin() as session:
    session.execute(delete(LoginSession).where(LoginSession.expires < now()))
    session.execute(delete(RateBucket).where(RateBucket.expires < now()))
    session.execute(delete(RoomSocketTicket).where(RoomSocketTicket.expires < now()))
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
