import copy
import itertools
import secrets
from datetime import timedelta
from types import SimpleNamespace
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from .main import Strict, authenticated, account_required, db, audit, limit
from .db import FriendGroup, GroupMember, Cup, Room, User, Achievement, MatchArchive, MatchPlayer, now, uid
from . import rooms, draft_turns
from .presets import PRESETS, rules, validate_pool
from .progression import ACHIEVEMENTS, stats, cup_standings, archive_room

router=APIRouter(prefix='/api')

def group_for(session, group_id, user_id, lock=False):
    stmt=select(FriendGroup).where(FriendGroup.id==str(group_id))
    group=session.scalar(stmt.with_for_update() if lock else stmt)
    if not group or not session.get(GroupMember,(group.id,user_id)): raise HTTPException(404,'Group not found')
    return group

def make_room(session,user_id,*,preset=None,group_id=None,cup_id=None,allowed=None,body=None,rules_version=draft_turns.RULES_VERSION):
    user=session.get(User,user_id)
    if body is None:
        body=SimpleNamespace(format='knockout',capacity=2,pick_seconds=30,competition=rules(preset)['competition'],name=user.username)
    state=rooms.new_state(user_id,body)
    state.update(draft_turns.initial(rules_version))
    state.update(preset=preset,groupId=group_id,cupId=cup_id)
    if allowed: state['allowedUsers']=allowed
    for _ in range(12):
        room=Room(owner_id=user_id,visibility='private',code=''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(4)),state=state)
        try:
            with session.begin_nested(): session.add(room); session.flush()
            return room
        except IntegrityError: continue
    raise HTTPException(503,'Unable to allocate a room. Try again.')

class GroupBody(Strict):
    name:str=Field(min_length=1,max_length=40)

class InviteBody(Strict):
    invite:str=Field(min_length=20,max_length=64,pattern=r'^[A-Za-z0-9_-]+$')

class CupBody(Strict):
    preset:Literal['open-ipl','under-85']='open-ipl'

@router.get('/presets')
def presets(): return [dict(id=key,**value) for key,value in PRESETS.items()]

@router.get('/groups')
def groups(auth=Depends(account_required),session=Depends(db)):
    rows=session.scalars(select(FriendGroup).join(GroupMember).where(GroupMember.user_id==auth.user_id).order_by(FriendGroup.created_at.desc())).all()
    return [dict(id=g.id,name=g.name) for g in rows]

@router.post('/groups',status_code=201)
def create_group(body:GroupBody,auth=Depends(account_required),session=Depends(db)):
    limit('group-create:'+auth.user_id,10,86400)
    name=body.name.strip()
    if not name: raise HTTPException(422,'Give your group a name')
    group=FriendGroup(name=name,owner_id=auth.user_id,invite=secrets.token_urlsafe(24))
    session.add(group); session.flush(); session.add(GroupMember(group_id=group.id,user_id=auth.user_id))
    audit(session,'group.created',auth.user_id,group.id); session.commit()
    return dict(id=group.id,name=group.name)

@router.post('/groups/join')
def join_group(body:InviteBody,auth=Depends(account_required),session=Depends(db)):
    limit('group-join:'+auth.user_id,30,300)
    group=session.scalar(select(FriendGroup).where(FriendGroup.invite==body.invite).with_for_update())
    if not group: raise HTTPException(404,'This invitation is no longer available')
    if not session.get(GroupMember,(group.id,auth.user_id)):
        count=session.scalar(select(func.count()).select_from(GroupMember).where(GroupMember.group_id==group.id))
        if count>=8: raise HTTPException(409,'This group already has eight players')
        session.add(GroupMember(group_id=group.id,user_id=auth.user_id)); audit(session,'group.joined',auth.user_id,group.id)
        session.commit()
    return dict(id=group.id,name=group.name)

@router.get('/groups/{group_id}')
def group_detail(group_id:UUID,auth=Depends(account_required),session=Depends(db)):
    group=group_for(session,group_id,auth.user_id)
    members=session.scalars(select(User).join(GroupMember).where(GroupMember.group_id==group.id).order_by(User.username)).all()
    cups=session.scalars(select(Cup).where(Cup.group_id==group.id).order_by(Cup.created_at.desc())).all()
    records=session.scalars(select(MatchArchive).where(MatchArchive.group_id==group.id).order_by(MatchArchive.created_at.desc())).all()
    rivals={}
    for record in records:
        d=record.data; pair=[p for p in d['players'] if p['userId']]
        if len(pair)!=2 or d.get('forfeit') or any(p.get('withdrew') for p in pair): continue
        pair.sort(key=lambda p:p['userId']); key=tuple(p['userId'] for p in pair)
        row=rivals.setdefault(key,dict(players=[dict(id=p['userId'],name=p['name']) for p in pair],played=0,wins={p['userId']:0 for p in pair}))
        row['played']+=1
        if d.get('winner') in row['wins']: row['wins'][d['winner']]+=1
    return dict(id=group.id,name=group.name,owner=group.owner_id==auth.user_id,you=auth.user_id,invite=group.invite,members=[dict(id=u.id,name=u.username) for u in members],
                cups=[dict(id=c.id,**c.state,standings=cup_standings(c.state)) for c in cups],rivalries=list(rivals.values()),
                history=[dict(id=r.id,createdAt=r.created_at,**r.data) for r in records[:20]])

@router.post('/groups/{group_id}/invite')
def rotate_invite(group_id:UUID,auth=Depends(account_required),session=Depends(db)):
    group=group_for(session,group_id,auth.user_id,True)
    if group.owner_id!=auth.user_id: raise HTTPException(403,'Only the group owner can replace its invitation')
    group.invite=secrets.token_urlsafe(24); session.commit(); return dict(invite=group.invite)

@router.post('/groups/{group_id}/cups',status_code=201)
def create_cup(group_id:UUID,body:CupBody,auth=Depends(account_required),session=Depends(db)):
    group=group_for(session,group_id,auth.user_id,True)
    if group.owner_id!=auth.user_id: raise HTTPException(403,'Only the group owner can start a cup')
    if session.scalar(select(Cup).where(Cup.group_id==group.id,Cup.state['status'].astext=='active')): raise HTTPException(409,'Finish or archive the current cup first')
    members=session.scalars(select(User).join(GroupMember).where(GroupMember.group_id==group.id).order_by(User.username)).all()
    if len(members)<2: raise HTTPException(409,'Invite at least one friend before starting a cup')
    if any(u.is_blocked for u in members): raise HTTPException(409,'A blocked account cannot enter a cup')
    validate_pool(session,body.preset,2)
    pairs=list(itertools.combinations([u.id for u in members],2))
    if len(members)==2: pairs=pairs*3
    state=dict(status='active',preset=body.preset,rulesVersion=draft_turns.RULES_VERSION,startsAt=now().isoformat(),endsAt=(now()+timedelta(days=14)).isoformat(),
               roster=[dict(id=u.id,name=u.username) for u in members],fixtures=[dict(id=uid(),a=a,b=b,status='pending',roomId=None) for a,b in pairs],winners=[])
    cup=Cup(group_id=group.id,state=state); session.add(cup); session.flush(); audit(session,'cup.created',auth.user_id,cup.id); session.commit()
    return dict(id=cup.id)

@router.post('/groups/{group_id}/cups/{cup_id}/{operation}')
def manage_cup(group_id:UUID,cup_id:UUID,operation:Literal['extend','archive'],auth=Depends(account_required),session=Depends(db)):
    group=group_for(session,group_id,auth.user_id)
    if group.owner_id!=auth.user_id: raise HTTPException(403,'Only the group owner can manage a cup')
    cup=session.scalar(select(Cup).where(Cup.id==str(cup_id),Cup.group_id==group.id).with_for_update())
    if not cup or cup.state['status']!='active': raise HTTPException(409,'No active cup')
    state=copy.deepcopy(cup.state)
    if operation=='extend':
        from datetime import datetime
        state['endsAt']=(max(now(),datetime.fromisoformat(state['endsAt']))+timedelta(days=7)).isoformat()
    else:
        if any(f['status']=='playing' and f.get('started') for f in state['fixtures']): raise HTTPException(409,'Finish or withdraw from started fixtures before archiving')
        state.update(status='unfinished',completedAt=now().isoformat())
    cup.state=state; audit(session,'cup.'+operation,auth.user_id,cup.id); session.commit(); return {'ok':True}

@router.post('/groups/{group_id}/fixtures/{fixture_id}')
def play_fixture(group_id:UUID,fixture_id:UUID,auth=Depends(account_required),session=Depends(db)):
    group=group_for(session,group_id,auth.user_id)
    cup=session.scalar(select(Cup).where(Cup.group_id==group.id,Cup.state['status'].astext=='active').with_for_update())
    if not cup: raise HTTPException(409,'No active cup')
    state=copy.deepcopy(cup.state)
    fixture=next((f for f in state['fixtures'] if f['id']==str(fixture_id)),None)
    if not fixture or auth.user_id not in [fixture['a'],fixture['b']]: raise HTTPException(403,'This fixture belongs to two other players')
    if fixture['status'] not in ['pending','playing']: raise HTTPException(409,'This fixture has already finished')
    if len(state['roster'])==2 and any(f['status']!='complete' for f in state['fixtures'][:state['fixtures'].index(fixture)]): raise HTTPException(409,'Finish the previous game in this series first')
    room=session.get(Room,fixture['roomId']) if fixture.get('roomId') else None
    if not room:
        validate_pool(session,state['preset'],2)
        room=make_room(session,auth.user_id,preset=state['preset'],group_id=group.id,cup_id=cup.id,allowed=[fixture['a'],fixture['b']],rules_version=state.get('rulesVersion',1))
        fixture.update(status='playing',roomId=room.id); cup.state=state
        audit(session,'fixture.opened',auth.user_id,cup.id); session.commit()
    return dict(code=room.code)

@router.post('/groups/{group_id}/friendly')
def friendly(group_id:UUID,body:CupBody,auth=Depends(account_required),session=Depends(db)):
    group=group_for(session,group_id,auth.user_id); limit('group-friendly:'+auth.user_id,20,3600)
    validate_pool(session,body.preset,2)
    room=make_room(session,auth.user_id,preset=body.preset,group_id=group.id)
    audit(session,'friendly.created',auth.user_id,room.id); session.commit(); return dict(code=room.code)

@router.post('/rooms/{room_id}/rematch')
def rematch(room_id:UUID,auth=Depends(authenticated),session=Depends(db)):
    from .room_routes import locked
    room=locked(session,room_id,auth.user_id)
    if room.state['phase']!='complete': raise HTTPException(409,'Finish this tournament first')
    archive_room(session,room)
    next_room=session.get(Room,room.state.get('rematchRoomId')) if room.state.get('rematchRoomId') else None
    if not next_room:
        limit('room-rematch:'+auth.user_id,20,3600)
        host=next(m for m in room.state['members'] if m['uid']==auth.user_id)
        body=SimpleNamespace(format=room.state['format'],capacity=room.state['capacity'],pick_seconds=room.state['seconds'],competition=room.state.get('competition'),name=host['name'])
        next_room=make_room(session,auth.user_id,preset=room.state.get('preset'),group_id=room.state.get('groupId'),body=body)
        next_room.visibility='private' if room.state.get('groupId') else room.visibility
        next_room.state={**next_room.state,'rematchOf':room.id}
        state=copy.deepcopy(room.state); state.update(rematchRoomId=next_room.id,rematchCode=next_room.code); room.state=state; room.version+=1
    audit(session,'room.rematch',auth.user_id,room.id); session.commit()
    # Joining remains explicit; the other participants see the same invitation.
    return dict(code=next_room.code)

@router.get('/progress')
def progress(auth=Depends(authenticated),session=Depends(db)):
    user=session.get(User,auth.user_id); values=stats(session,auth.user_id)
    unlocked={a.code:a for a in session.scalars(select(Achievement).where(Achievement.user_id==auth.user_id))}
    achievements=[]
    for definition in ACHIEVEMENTS:
        earned=unlocked.get(definition['code'])
        achievements.append(dict(**definition,earnedAt=earned.earned_at if earned else None,progress=definition['target'] if earned else min(definition['target'],values.get(definition['metric'],0))))
    history=session.scalars(select(MatchArchive).join(MatchPlayer).where(MatchPlayer.user_id==auth.user_id).order_by(MatchArchive.created_at.desc()).limit(30)).all()
    return dict(guest=user.is_guest,name='Guest player' if user.is_guest else user.username,stats=values,achievements=achievements,history=[dict(id=r.id,createdAt=r.created_at,**r.data) for r in history])

@router.post('/achievements/{code}/share')
def share_achievement(code:str,auth=Depends(authenticated),session=Depends(db)):
    earned=session.scalar(select(Achievement).where(Achievement.user_id==auth.user_id,Achievement.code==code).with_for_update())
    if not earned: raise HTTPException(409,'Earn this trophy before sharing an achievement card')
    if not earned.share_token: earned.share_token=secrets.token_urlsafe(24)
    audit(session,'achievement.shared',auth.user_id); session.commit()
    return dict(path='/share/achievement/'+earned.share_token)

@router.get('/shares/achievements/{token}')
def public_achievement(token:str,session=Depends(db)):
    if len(token)>64: raise HTTPException(404,'Achievement not found')
    earned=session.scalar(select(Achievement).where(Achievement.share_token==token))
    if not earned: raise HTTPException(404,'Achievement not found')
    user=session.get(User,earned.user_id)
    if not user or user.is_blocked: raise HTTPException(404,'Achievement not found')
    definition=next(d for d in ACHIEVEMENTS if d['code']==earned.code)
    return dict(**definition,name='Guest player' if user.is_guest else user.username,earnedAt=earned.earned_at)
