"""Claim browser guest progress after proving ownership of an existing account."""
import copy
from sqlalchemy import select, update, delete
from sqlalchemy.dialects.postgresql import insert
from fastapi import HTTPException
from .db import Game, Room, MatchPlayer, MatchArchive, Achievement, LoginSession, Audit

def claim_guest(session,guest,account):
    rooms=session.scalars(select(Room).where(Room.state['members'].contains([{'uid':guest.id}]) | Room.state['members'].contains([{'userId':guest.id}])).order_by(Room.id).with_for_update()).all()
    records=session.scalars(select(MatchArchive).join(MatchPlayer).where(MatchPlayer.user_id==guest.id).with_for_update()).all()
    if any(any(m.get('userId',m.get('uid'))==account.id for m in r.state['members']) for r in rooms) or any(any(p['userId']==account.id for p in r.data['players']) for r in records):
        raise HTTPException(409,'These accounts have played each other, so their records cannot be combined. Sign out of the guest session before signing in to this account.')
    session.execute(update(Game).where(Game.owner_id==guest.id).values(owner_id=account.id))
    for room in rooms:
        state=copy.deepcopy(room.state)
        for member in state['members']:
            if member.get('uid')==guest.id: member['uid']=account.id
            if member.get('userId')==guest.id: member['userId']=account.id
        room.state=state; room.version+=1
    session.execute(update(Room).where(Room.owner_id==guest.id).values(owner_id=account.id))
    for record in records:
        data=copy.deepcopy(record.data)
        for player in data['players']:
            if player['userId']==guest.id: player['userId']=account.id
        if data.get('winner')==guest.id: data['winner']=account.id
        record.data=data
    session.execute(update(MatchPlayer).where(MatchPlayer.user_id==guest.id).values(user_id=account.id))
    for earned in session.scalars(select(Achievement).where(Achievement.user_id==guest.id)):
        session.execute(insert(Achievement).values(user_id=account.id,code=earned.code,earned_at=earned.earned_at,source=earned.source).on_conflict_do_nothing(index_elements=['user_id','code']))
        # Preserve the guest link when the account has not shared this trophy.
        target=session.get(Achievement,(account.id,earned.code))
        if not target.share_token and earned.share_token:
            token=earned.share_token; earned.share_token=None; session.flush(); target.share_token=token
        session.delete(earned)
    session.execute(delete(LoginSession).where(LoginSession.user_id==guest.id))
    session.flush()
    from .progression import award_match
    award_match(session,[account.id],account.id)
    session.add(Audit(action='guest.claimed',actor=account.id))
