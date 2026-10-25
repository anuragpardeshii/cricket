import asyncio
from contextlib import asynccontextmanager
import copy
import hashlib
import hmac
import logging
import os
import re
import secrets
from datetime import timedelta
from typing import Literal
from uuid import UUID
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import select, delete, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .db import Session, User, LoginSession, Game, Room, Audit, RateBucket, now, uid
from .game import initial, act, advance_game
from .catalog import load_catalog
from .draft_pool import used_people, person_key, validate_edition

ENV=os.getenv('APP_ENV','development')
ORIGIN=os.getenv('APP_ORIGIN','http://localhost:5173').rstrip('/')
SECURE=ENV=='production'
if ENV not in ('development','test','production') or (SECURE and not ORIGIN.startswith('https://')):
    raise RuntimeError('Invalid environment or production origin')
COOKIE='__Host-out_session' if SECURE else 'out_session'
@asynccontextmanager
async def lifespan(app):
    from .realtime import RoomSignals, listen
    from .voice import monitor
    signals = RoomSignals()
    app.state.room_signals = signals
    async def clock():
        from .rooms import tick
        from .game import tick as practice_tick
        while True:
            try: await asyncio.to_thread(tick)
            except Exception: logging.getLogger('out.security').error('room_clock_failed')
            try: await asyncio.to_thread(practice_tick)
            except Exception: logging.getLogger('out.security').error('practice_clock_failed')
            await asyncio.sleep(1)
    tasks=[asyncio.create_task(clock()), asyncio.create_task(listen(signals)), asyncio.create_task(monitor(signals))]
    try:
        yield
    finally:
        for task in tasks: task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

app=FastAPI(lifespan=lifespan,title='OUT Cricket API',version='1.0.0',docs_url=None if SECURE else '/api/docs',openapi_url=None if SECURE else '/api/openapi.json',redoc_url=None)
allowed_hosts={host.strip() for host in os.getenv('ALLOWED_HOSTS','localhost,127.0.0.1,testserver,api').split(',') if host.strip()}
if render_host := os.getenv('RENDER_EXTERNAL_HOSTNAME'):
    allowed_hosts.add(render_host)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=sorted(allowed_hosts))
ph=PasswordHasher(time_cost=3,memory_cost=65536,parallelism=2)
DUMMY=ph.hash(secrets.token_urlsafe(32))
log=logging.getLogger('out.security')
def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def db():
    with Session() as session: yield session

def audit(session,action,actor=None,resource=None):
    session.add(Audit(action=action,actor=actor,resource=resource))
    log.info('security action=%s actor=%s resource=%s',action,actor,resource)

def limit(key, maximum, seconds=60):
    timestamp=int(now().timestamp()); window=timestamp//seconds
    with Session.begin() as session:
        stmt=insert(RateBucket).values(key=digest(f'{key}:{window}'),count=1,expires=now()+timedelta(seconds=seconds*2))
        count=session.scalar(stmt.on_conflict_do_update(index_elements=[RateBucket.key],set_={'count':RateBucket.count+1}).returning(RateBucket.count))
    if count>maximum: raise HTTPException(429,'Too many requests',headers={'Retry-After':str(seconds)})

@app.middleware('http')
async def boundary(request,call_next):
    request_id=secrets.token_hex(12)
    try:
        if request.method not in ('GET','HEAD','OPTIONS'):
            if request.headers.get('origin') != ORIGIN or request.headers.get('x-out-request') != '1':
                raise HTTPException(403,'Request origin rejected')
            if request.headers.get('content-type','').split(';')[0] != 'application/json':
                raise HTTPException(415,'JSON required')
        # Bound actual streamed bytes, including requests without Content-Length.
        body=bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body)>16384: raise HTTPException(413,'Request too large')
        request._body=bytes(body)
        response=await call_next(request)
    except HTTPException as exc:
        response=JSONResponse({'detail':exc.detail},status_code=exc.status_code,headers=exc.headers)
    except Exception:
        # Do not log exception parameters, SQL statements, credentials, or bodies.
        log.error('request_failed request_id=%s',request_id)
        response=JSONResponse({'detail':'Service unavailable','request_id':request_id},status_code=503)
    response.headers.update({'X-Request-ID':request_id,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'"})
    if SECURE: response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
    return response

@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):
    return JSONResponse({'detail':'Invalid request fields'},status_code=422)

class Strict(BaseModel): model_config=ConfigDict(extra='forbid',strict=True)
class Register(Strict):
    username: str=Field(pattern=r'^[A-Za-z0-9._-]{3,24}$')
    email: EmailStr=Field(max_length=254)
    phone: str=Field(pattern=r'^[0-9]{10}$')
    country_code: str=Field(default='+91',pattern=r'^\+[1-9][0-9]{0,3}$')
    password: str=Field(min_length=7,max_length=128)
    @field_validator('password')
    @classmethod
    def password_valid(cls,v):
        if len(set(v))==1 or v.lower() in {'passwordpassword','password123456789','123456789012345','qwertyuiopasdfgh'}: raise ValueError('Weak password')
        return v
class Login(Strict):
    email: EmailStr=Field(max_length=254)
    password: str=Field(min_length=1,max_length=128)
class Action(Strict):
    action: Literal['start','roll','pick','match','formation','exit']
    version: int=Field(ge=0)
    player_id: str | None=Field(default=None,max_length=16)
    slot_id: str | None=Field(default=None,max_length=8)
    order: list[str] | None=Field(default=None,min_length=11,max_length=11)

def authenticated(request:Request,session=Depends(db)):
    token=request.cookies.get(COOKIE,'')
    auth=session.get(LoginSession,digest(token)) if token else None
    if not auth or auth.expires<=now(): raise HTTPException(401,'Sign in required')
    user=session.get(User,auth.user_id)
    if not user or user.is_blocked: raise HTTPException(403,'Account blocked. Contact an administrator.')
    if request.method not in ('GET','HEAD') and not hmac.compare_digest(request.headers.get('x-csrf-token',''),auth.csrf): raise HTTPException(403,'Invalid CSRF token')
    limit('user:'+auth.user_id,180)
    return auth

def issue(session,user,response,request):
    old=request.cookies.get(COOKIE)
    if old: session.execute(delete(LoginSession).where(LoginSession.token_hash==digest(old)))
    token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(32)
    session.add(LoginSession(token_hash=digest(token),user_id=user.id,csrf=csrf,expires=now()+timedelta(hours=12)))
    response.set_cookie(COOKIE,token,httponly=True,secure=SECURE,samesite='strict',max_age=43200,path='/')
    ua=request.headers.get('user-agent','').lower()
    device='Tablet' if 'ipad' in ua or 'tablet' in ua else 'Mobile' if 'mobile' in ua else 'Desktop'
    session.add(Audit(action='session.started',actor=user.id,details={'device':device,'audience':'Guest' if user.is_guest else 'Registered'}))
    return session_view(user, csrf)

def session_view(user, csrf):
    return dict(user=None if user.is_guest else dict(id=user.id,username=user.username,is_admin=user.is_admin),csrf=csrf,guest=user.is_guest)

def account_required(auth=Depends(authenticated),session=Depends(db)):
    if session.get(User,auth.user_id).is_guest: raise HTTPException(403,'Sign in to view account activity')
    return auth

@app.post('/api/auth/guest')
def guest(request:Request,response:Response,session=Depends(db)):
    limit('guest-ip:'+request.client.host,20,3600)
    token=request.cookies.get(COOKIE,'')
    existing=session.get(LoginSession,digest(token)) if token else None
    if existing and existing.expires>now():
        user=session.get(User,existing.user_id)
        if user.is_blocked: raise HTTPException(403,'Account blocked. Contact an administrator.')
        return session_view(user,existing.csrf)
    identity=uid()
    user=User(id=identity,is_guest=True,username='guest-'+secrets.token_hex(8),email=identity+'@guest.invalid',password_hash='!guest-login-disabled')
    session.add(user); session.flush()
    result=issue(session,user,response,request)
    audit(session,'guest.created',user.id); session.commit()
    return result

@app.get('/api/health')
def health(session=Depends(db)):
    session.execute(select(1)); return {'status':'ok'}
@app.post('/api/auth/register',status_code=201)
def register(body:Register,request:Request,response:Response,session=Depends(db)):
    limit('auth-ip:'+request.client.host,10,300)
    user=User(username=body.username.lower(),email=str(body.email).lower(),password_hash=ph.hash(body.password),mobile=body.country_code+body.phone)
    # Store a normalized country-code + national number; DB uniqueness handles concurrent signups.
    session.add(user)
    try:
        session.flush(); result=issue(session,user,response,request); audit(session,'account.created',user.id); session.commit()
    except IntegrityError:
        session.rollback(); raise HTTPException(409,'Unable to register with those details')
    return result
@app.post('/api/auth/login')
def login(body:Login,request:Request,response:Response,session=Depends(db)):
    limit('auth-ip:'+request.client.host,10,300)
    limit('auth-account:'+str(body.email).lower(),10,300)
    user=session.scalar(select(User).where(User.email==str(body.email).lower()).with_for_update())
    try: valid=ph.verify(user.password_hash if user and not user.is_guest else DUMMY,body.password)
    except (VerifyMismatchError,InvalidHashError): valid=False
    if not valid or not user or user.is_guest:
        audit(session,'login.failed'); session.commit(); raise HTTPException(401,'Invalid email or password')
    if user.is_blocked:
        audit(session,'login.blocked',user.id); session.commit(); raise HTTPException(403,'Account blocked. Contact an administrator.')
    result=issue(session,user,response,request); audit(session,'login.success',user.id); session.commit(); return result
@app.get('/api/auth/me')
def me(auth=Depends(authenticated),session=Depends(db)):
    user=session.get(User,auth.user_id); return session_view(user,auth.csrf)
@app.post('/api/auth/logout')
def logout(response:Response,auth=Depends(authenticated),session=Depends(db)):
    session.delete(auth); audit(session,'logout',auth.user_id); session.commit(); response.delete_cookie(COOKIE,path='/',secure=SECURE,httponly=True,samesite='strict'); return {'ok':True}

def view(game):
    state=copy.deepcopy(game.state)
    if state.get('rolled'):
        state['rolled']['players']=[p for p in state['rolled']['players'] if p['id'] not in state['taken'] and person_key(p) not in used_people([state['yourXI'],state['opponentXI']])]
    return dict(id=game.id,version=game.version,state=state,opponentCount=len(game.state['opponentXI']))
def owned(session,game_id,user_id,lock=False):
    stmt=select(Game).where(Game.id==str(game_id),Game.owner_id==user_id)
    game=session.scalar(stmt.with_for_update() if lock else stmt)
    if not game:
        audit(session,'game.access_denied',user_id); session.commit(); raise HTTPException(404,'Game not found')
    return game
@app.get('/api/catalog')
def catalog(competition:Literal['odi','t20','ipl']|None=None,edition:int|None=None,auth=Depends(authenticated),session=Depends(db)):
    try: validate_edition(competition,edition)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return load_catalog(session,competition,edition)
class CreateGame(Strict):
    competition:Literal['odi','t20','ipl']='odi'
    edition:int|None=None

@app.post('/api/games',status_code=201)
def create(body:CreateGame=CreateGame(),auth=Depends(authenticated),session=Depends(db)):
    limit('create:'+auth.user_id,20,3600)
    # Practice is one simple format: a T20 draft across every historical T20
    # World Cup edition. Keep accepting the old request fields during rollout.
    game=Game(owner_id=auth.user_id,state=initial('t20',None))
    session.add(game); session.flush(); audit(session,'game.created',auth.user_id,game.id); session.commit(); return view(game)
@app.get('/api/games')
def games(auth=Depends(authenticated),session=Depends(db)):
    return [dict(id=g.id,screen=g.state['screen'],created_at=g.created_at) for g in session.scalars(select(Game).where(Game.owner_id==auth.user_id).order_by(Game.created_at.desc()).limit(50))]
@app.get('/api/games/{game_id}')
def get_game(game_id:UUID,auth=Depends(authenticated),session=Depends(db)):
    game=owned(session,game_id,auth.user_id,True)
    if advance_game(session,game): session.commit()
    return view(game)
@app.post('/api/games/{game_id}/actions')
def action(game_id:UUID,body:Action,auth=Depends(authenticated),session=Depends(db)):
    game=owned(session,game_id,auth.user_id,True)
    if advance_game(session,game):
        session.commit()
        raise HTTPException(409,'Game changed; refresh and try again')
    if game.version!=body.version: raise HTTPException(409,'Game changed; refresh and try again')
    state=copy.deepcopy(game.state)
    needs_pool=body.action in ['roll','pick'] and state.get('screen')=='draft' and state.get('turn')=='you'
    squads=load_catalog(session,state.get('competition'),state.get('edition'))['squads'] if needs_pool else []
    act(state,body.action,body.player_id,body.slot_id,squads=squads,order=body.order)
    game.state=state; game.version+=1; audit(session,'game.'+body.action,auth.user_id,game.id); session.commit(); return view(game)
def admin_required(auth=Depends(authenticated),session=Depends(db)):
    user=session.get(User,auth.user_id)
    if user.is_guest or not user.is_admin: raise HTTPException(403,'Administrator access required')
    return auth

@app.get('/api/dashboard',dependencies=[Depends(admin_required)])
@app.get('/api/admin/analytics',dependencies=[Depends(admin_required)])
def dashboard(days:Literal['7','30','90']='30',session=Depends(db)):
    from datetime import datetime,timezone
    from collections import Counter
    cutoff=now()-timedelta(days=int(days))
    count=lambda stmt: session.scalar(stmt) or 0
    total=count(select(func.count()).select_from(User).where(User.is_guest.is_(False)))
    new=count(select(func.count()).select_from(User).where(User.is_guest.is_(False),User.created_at>=cutoff))
    events=list(session.scalars(select(Audit).where(Audit.created_at>=cutoff).order_by(Audit.created_at.desc()).limit(50000)))
    games=list(session.scalars(select(Game).where(Game.created_at>=cutoff).limit(10000)))
    rooms=list(session.scalars(select(Room).where(Room.created_at>=cutoff).limit(10000)))
    starts=[e for e in events if e.action=='session.started']; devices=Counter(e.details.get('device','Unknown') for e in starts); audience=Counter(e.details.get('audience','Unknown') for e in starts)
    trend=[]
    for offset in range(int(days)-1,-1,-1):
        date=(now()-timedelta(days=offset)).date()
        registrations=count(select(func.count()).select_from(User).where(User.is_guest.is_(False),func.date(User.created_at)==date))
        active=len({e.actor for e in events if e.created_at.date()==date and e.actor})
        trend.append(dict(label=date.strftime('%d %b'),registrations=registrations,activePlayers=active))
    popular=Counter(p['squad'] for g in games for p in g.state['yourXI'].values())
    for room in rooms:
        popular.update(p['squad'] for m in room.state['members'] for p in m['xi'].values())
    completed=sum(bool(g.state.get('match')) for g in games)+sum(m['status']=='complete' for r in rooms for m in r.state['matches'])
    colors=['#f5a623','#83a9c7','#7bbba0','#a6a1cf']
    segments=lambda counts:[dict(label=k,value=round(v/max(1,sum(counts.values()))*100,1),color=colors[i%4]) for i,(k,v) in enumerate(counts.items())]
    return dict(totalRegistered=total,newRegistrations=new,activePlayers=len({e.actor for e in events if e.actor}),sessions=len(starts),draftStarts=sum(g.state['screen']!='lobby' for g in games)+sum(r.state['phase'] not in ['lobby','expired'] for r in rooms),matchesFinished=completed,rooms=len(rooms),liveRooms=sum(r.state['phase']=='live' for r in rooms),trend=trend,devices=segments(devices),audience=segments(audience),popular=[dict(name=k,picks=v) for k,v in popular.most_common(8)],sampleLimit=50000)

class BlockUser(Strict):
    blocked: bool

class GrantAdmin(Strict):
    pass

@app.get('/api/admin/users',dependencies=[Depends(admin_required)])
def admin_users(page:int=Query(1,ge=1,le=100000),page_size:int=Query(10,ge=1,le=50),session=Depends(db)):
    total=session.scalar(select(func.count()).select_from(User).where(User.is_guest.is_(False)))
    users=session.scalars(select(User).where(User.is_guest.is_(False)).order_by(User.created_at.desc(),User.id).offset((page-1)*page_size).limit(page_size)).all()
    return dict(page=page,page_size=page_size,total=total,users=[dict(id=u.id,username=u.username,email=u.email,mobile=u.mobile,is_admin=u.is_admin,is_blocked=u.is_blocked,created_at=u.created_at) for u in users])

@app.post('/api/admin/users/{user_id}/status')
def block_user(user_id:UUID,body:BlockUser,auth=Depends(admin_required),session=Depends(db)):
    user=session.scalar(select(User).where(User.id==str(user_id),User.is_guest.is_(False)).with_for_update())
    if not user: raise HTTPException(404,'User not found')
    if user.id==auth.user_id or user.is_admin: raise HTTPException(409,'Administrator accounts are protected from blocking')
    user.is_blocked=body.blocked
    if body.blocked: session.execute(delete(LoginSession).where(LoginSession.user_id==user.id))
    session.add(Audit(action='user.blocked' if body.blocked else 'user.unblocked',actor=auth.user_id,resource=user.id))
    session.commit(); return dict(id=user.id,is_blocked=user.is_blocked)

@app.post('/api/admin/users/{user_id}/admin')
def grant_admin(user_id:UUID,body:GrantAdmin,auth=Depends(admin_required),session=Depends(db)):
    limit('admin-grant:'+auth.user_id,20,3600)
    user=session.scalar(select(User).where(User.id==str(user_id),User.is_guest.is_(False)).with_for_update())
    if not user: raise HTTPException(404,'User not found')
    if user.is_blocked: raise HTTPException(409,'Unblock this account before granting administrator access')
    if not user.is_admin:
        user.is_admin=True
        session.add(Audit(action='admin.granted',actor=auth.user_id,resource=user.id,details={'source':'dashboard'}))
        session.commit()
    return dict(id=user.id,is_admin=True)

from .room_routes import router as room_router
app.include_router(room_router)
from .realtime import router as realtime_router
from .voice import router as voice_router
app.include_router(realtime_router)
app.include_router(voice_router)
