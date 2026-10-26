import copy
import secrets
import time
from typing import Literal
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Query,Request
from pydantic import Field,model_validator
from sqlalchemy import select,func,cast,Float
from sqlalchemy.exc import IntegrityError
from .main import Strict,authenticated,db,limit,audit
from .db import Room,User
from .catalog import load_catalog
from .draft_pool import validate_edition
from .presets import rules,validate_pool
from .progression import archive_room
from . import rooms
router=APIRouter(prefix='/api/rooms',dependencies=[Depends(authenticated)])
class CreateRoom(Strict):
    name:str|None=Field(default=None,min_length=1,max_length=24,pattern=r'^[A-Za-z0-9 ._-]+$')
    visibility:Literal['public','private']='private'
    format:Literal['league','knockout']
    capacity:int=Field(ge=2,le=8)
    pick_seconds:int=Field(ge=10,le=120)
    competition:Literal['t20','odi','ipl']='odi'
    edition:int|None=None
    preset:Literal['open-ipl','under-85']|None=None
    lobby_minutes:int|None=Field(default=None,ge=1,le=30)  # Accepted for older clients; ignored.
    @model_validator(mode='after')
    def check(self):
        # Rooms always draw from every historical edition in the competition.
        # Accept the old edition field during a staggered frontend rollout.
        validate_edition(self.competition,None)
        if self.name is not None and not self.name.strip(): raise ValueError('Name required')
        if self.format=='knockout' and self.capacity not in [2,4,8]: raise ValueError('Knockout requires 2, 4 or 8 teams')
        return self
class JoinRoom(Strict):
    code:str=Field(pattern=r'^[A-Z2-9]{4}$')
    name:str|None=Field(default=None,min_length=1,max_length=24,pattern=r'^[A-Za-z0-9 ._-]+$')
class RoomAction(Strict):
    action:Literal['start','roll','pick','formation']
    version:int=Field(ge=0)
    draft_revision:int|None=Field(default=None,ge=0)
    player_id:str|None=Field(default=None,max_length=16)
    slot_id:str|None=Field(default=None,max_length=8)
    order:list[str]|None=Field(default=None,min_length=11,max_length=11)
def locked(session,room_id,user_id):
    room=session.scalar(select(Room).where(Room.id==str(room_id)).with_for_update())
    if room and user_id in room.state.get('removedUsers',[]): raise HTTPException(403,'You have exited or been removed from this room.')
    if not room or not any(m['uid']==user_id for m in room.state['members']): raise HTTPException(404,'Room not found')
    return room
@router.post('',status_code=201)
def create(body:CreateRoom,auth=Depends(authenticated),session=Depends(db)):
    limit('room-create:'+auth.user_id,10,3600)
    user=session.get(User,auth.user_id)
    body.name=user.username if not user.is_guest else 'Player 1'
    if body.preset:
        validate_pool(session,body.preset,body.capacity); body.competition=rules(body.preset)['competition']
    for _ in range(12):
        room=Room(owner_id=auth.user_id,visibility=body.visibility,code=''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(4)),state=rooms.new_state(auth.user_id,body))
        room.state['preset']=body.preset
        try:
            with session.begin_nested(): session.add(room); session.flush()
            break
        except IntegrityError: continue
    else: raise HTTPException(503,'Unable to allocate a room code. Try again.')
    audit(session,'room.created',auth.user_id,room.id); session.commit()
    return rooms.project(room,auth.user_id,time.time())
@router.post('/join')
def join(body:JoinRoom,request:Request,auth=Depends(authenticated),session=Depends(db)):
    limit('room-join:'+auth.user_id,30,300)
    limit('room-join-ip:'+request.client.host,60,300)
    room=session.scalar(select(Room).where(Room.code==body.code).with_for_update())
    if not room: raise HTTPException(404,'Room not found. Check the four-character code and try again.')
    state=copy.deepcopy(room.state)
    if state.get('allowedUsers') and auth.user_id not in state['allowedUsers']: raise HTTPException(403,'This room is reserved for the scheduled cup players')
    if state.get('groupId'):
        from .community_routes import group_for
        group_for(session,state['groupId'],auth.user_id)
    if auth.user_id in state.get('removedUsers',[]): raise HTTPException(403,'You have exited or been removed from this room.')
    if any(m['uid']==auth.user_id for m in state['members']): return rooms.project(room,auth.user_id,time.time())
    if state['phase'] in ['draft','live']: raise HTTPException(409,'Game in progress. New players cannot join after the draft starts.')
    if state['phase']=='complete': raise HTTPException(409,'This tournament has finished. Join another room or create your own.')
    if state['phase']!='lobby': raise HTTPException(409,'This room has expired. Join another room or create your own.')
    if len(state['members'])>=state['capacity']: raise HTTPException(409,'Room is full. All player seats have been taken.')
    user=session.get(User,auth.user_id)
    preferred=user.username if not user.is_guest else f"Player {len(state['members'])+1}"
    name=preferred; suffix=2
    while any(m['name'].lower()==name.lower() for m in state['members']):
        name=f"Player {len(state['members'])+suffix}" if user.is_guest else f"{preferred[:20]} {suffix}"; suffix+=1
    state['members'].append(rooms.member(auth.user_id,name)); room.state=state; room.version+=1
    audit(session,'room.joined',auth.user_id,room.id); session.commit(); return rooms.project(room,auth.user_id,time.time())
@router.get('/public')
def public_rooms(page:int=Query(1,ge=1,le=10000),page_size:int=Query(10,ge=1,le=25),session=Depends(db)):
    conditions=[Room.visibility=='public',Room.state['phase'].astext=='lobby',func.jsonb_array_length(Room.state['members'])<cast(Room.state['capacity'].astext,Float)]
    total=session.scalar(select(func.count()).select_from(Room).where(*conditions))
    rows=session.scalars(select(Room).where(*conditions).order_by(Room.created_at.desc(),Room.id).offset((page-1)*page_size).limit(page_size)).all()
    # No identities, membership IDs, private room codes or game state in discovery.
    return dict(page=page,page_size=page_size,total=total,rooms=[dict(code=r.code,format=r.state['format'],capacity=r.state['capacity'],players=len(r.state['members']),pick_seconds=r.state['seconds'],competition=r.state.get('competition'),edition=r.state.get('edition')) for r in rows])

class Rename(Strict):
    name:str=Field(min_length=1,max_length=24,pattern=r'^[A-Za-z0-9 ._-]+$')

class Ready(Strict):
    ready:bool

@router.post('/{room_id}/ready')
def ready(room_id:UUID,body:Ready,auth=Depends(authenticated),session=Depends(db)):
    room=locked(session,room_id,auth.user_id); state=copy.deepcopy(room.state)
    if state['phase']!='lobby': raise HTTPException(409,'Readiness is locked once the draft starts')
    person=next(m for m in state['members'] if m['uid']==auth.user_id)
    if person.get('ready',False)!=body.ready:
        person['ready']=body.ready; room.state=state; room.version+=1
        audit(session,'room.ready',auth.user_id,room.id); session.commit()
    return rooms.project(room,auth.user_id,time.time())

@router.post('/{room_id}/name')
def rename(room_id:UUID,body:Rename,auth=Depends(authenticated),session=Depends(db)):
    limit('room-rename:'+auth.user_id,10,60)
    room=locked(session,room_id,auth.user_id); state=copy.deepcopy(room.state); name=body.name.strip()
    if state['phase']!='lobby': raise HTTPException(409,'Names are locked once player selection starts')
    if not name or any(m['name'].lower()==name.lower() and m['uid']!=auth.user_id for m in state['members']): raise HTTPException(409,'Choose a different name')
    person=next(m for m in state['members'] if m['uid']==auth.user_id); person['name']=name
    room.state=state; room.version+=1; audit(session,'room.renamed',auth.user_id,room.id); session.commit()
    return rooms.project(room,auth.user_id,time.time())

@router.get('/{room_id}')
def get(room_id:UUID,auth=Depends(authenticated),session=Depends(db)):
    room=locked(session,room_id,auth.user_id)
    if room.state['phase']=='complete': archive_room(session,room); session.commit()
    return rooms.project(room,auth.user_id,time.time())
@router.post('/{room_id}/actions')
def action(room_id:UUID,body:RoomAction,auth=Depends(authenticated),session=Depends(db)):
    room=locked(session,room_id,auth.user_id); state=copy.deepcopy(room.state); ts=time.time()
    your_pick=body.action in ['roll','pick'] and state['phase']=='draft' and state['members'][state['turn']]['uid']==auth.user_id
    needs_pool=state['phase']=='draft' and (ts>=state['deadline'] or your_pick)
    players=[p for s in load_catalog(session,state.get('competition'),state.get('edition'))['squads'] for p in s['players']] if needs_pool else []
    if rooms.advance(state,players,ts):
        room.state=state; room.version+=1; archive_room(session,room); session.commit()
        raise HTTPException(409,'The room advanced. Refresh and try again.')
    # Picks depend on the turn and rolled squad, not another team's formation,
    # name or vote. Keep a separate revision, while supporting older clients.
    if body.action in ['roll','pick'] and body.draft_revision is not None:
        if state.get('draftRevision',0)!=body.draft_revision: raise HTTPException(409,'The draft advanced. Try again.')
    elif room.version!=body.version: raise HTTPException(409,'Room changed. Try again.')
    if body.action=='start':
        if room.owner_id!=auth.user_id: raise HTTPException(403,'Only the host can start')
        if state.get('cupId'):
            from .db import Cup
            cup=session.scalar(select(Cup).where(Cup.id==state['cupId']).with_for_update())
            if not cup or cup.state['status']!='active': raise HTTPException(409,'This cup has ended. Return to your group to start a new match.')
            cup_state=copy.deepcopy(cup.state)
            fixture=next((f for f in cup_state['fixtures'] if f.get('roomId')==room.id),None)
            if not fixture or fixture['status']!='playing': raise HTTPException(409,'This fixture is no longer available')
            fixture['started']=True; cup.state=cup_state
        rooms.start(state,ts)
    elif body.action=='formation':
        if state['phase']!='draft': raise HTTPException(409,'Batting order is locked once matches start')
        person=next(m for m in state['members'] if m['uid']==auth.user_id)
        person['order']=rooms.validate_order(body.order)
    else:
        if state['phase']!='draft' or state['members'][state['turn']]['uid']!=auth.user_id: raise HTTPException(403,'Wait for your turn')
        if body.action=='roll': rooms.roll(state,players,ts=ts)
        else: rooms.pick(state,players,ts,body.player_id,body.slot_id)
    room.state=state; room.version+=1; archive_room(session,room); audit(session,'room.'+body.action,auth.user_id,room.id); session.commit()
    return rooms.project(room,auth.user_id,ts)

class KickVote(Strict):
    target_id:str=Field(min_length=36,max_length=36)

@router.post('/{room_id}/kick-vote')
def kick_vote(room_id:UUID,body:KickVote,auth=Depends(authenticated),session=Depends(db)):
    limit('kick-vote:'+auth.user_id,30,300)
    room=locked(session,room_id,auth.user_id); state=copy.deepcopy(room.state); ts=time.time()
    players=[p for s in load_catalog(session,state.get('competition'),state.get('edition'))['squads'] for p in s['players']] if state['phase']=='draft' and ts>=state['deadline'] else []
    rooms.advance(state,players,ts)
    passed=rooms.vote_kick(room,state,auth.user_id,body.target_id,ts)
    rooms.advance(state,players,ts)
    room.state=state; room.version+=1
    archive_room(session,room)
    session.add(rooms.Audit(action='room.kicked' if passed else 'room.kick_vote',actor=auth.user_id,resource=room.id,details={'target':body.target_id}))
    session.commit(); return rooms.project(room,auth.user_id,ts)

@router.post('/{room_id}/exit')
def exit_room(room_id:UUID,auth=Depends(authenticated),session=Depends(db)):
    room=locked(session,room_id,auth.user_id); state=copy.deepcopy(room.state); ts=time.time()
    players=[p for s in load_catalog(session,state.get('competition'),state.get('edition'))['squads'] for p in s['players']] if state['phase']=='draft' and ts>=state['deadline'] else []
    rooms.advance(state,players,ts)
    target=next(m for m in state['members'] if m['uid']==auth.user_id)
    if state.get('cupId') and state['phase']=='lobby':
        # Leaving before a draft starts is a cancellation, never a scored loss.
        from .db import Cup
        cup=session.scalar(select(Cup).where(Cup.id==state['cupId']).with_for_update())
        if cup:
            cup_state=copy.deepcopy(cup.state)
            for fixture in cup_state['fixtures']:
                if fixture.get('roomId')==room.id: fixture.update(status='pending',roomId=None)
            cup.state=cup_state
        session.delete(room); session.commit(); return {'ok':True,'closed':True}
    rooms.remove_member(room,state,target,ts,'exited'); rooms.advance(state,players,ts)
    room.state=state; archive_room(session,room)
    if not any(member['uid'] is not None for member in state['members']):
        audit(session,'room.closed',auth.user_id,room.id); session.delete(room); session.commit()
        return {'ok':True,'closed':True}
    room.state=state; room.version+=1; audit(session,'room.exited',auth.user_id,room.id); session.commit()
    return {'ok':True,'closed':False}
