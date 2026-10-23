import os
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, String, DateTime, ForeignKey, Integer, CheckConstraint, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

def now(): return datetime.now(timezone.utc)
def uid(): return str(uuid.uuid4())
database_url = os.environ['DATABASE_URL']
if database_url.startswith('postgresql://'):
    database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
elif database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql+psycopg://', 1)
connect_args = {'options': '-c statement_timeout=5000 -c lock_timeout=3000'}
if sslmode := os.getenv('DATABASE_SSLMODE'):
    connect_args['sslmode'] = sslmode
engine = create_engine(database_url, pool_pre_ping=True, pool_size=10, max_overflow=10, connect_args=connect_args)
Session = sessionmaker(engine)
class Base(DeclarativeBase): pass
class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    mobile: Mapped[str | None] = mapped_column(String(16), unique=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    is_guest: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false', index=True)
    username: Mapped[str] = mapped_column(String(24), unique=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
class LoginSession(Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    csrf: Mapped[str] = mapped_column(String(64))
    expires: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
class Game(Base):
    __tablename__ = 'games'
    __table_args__ = (CheckConstraint('version >= 0'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    code: Mapped[str | None] = mapped_column(String(8), unique=True)
    version: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
class Audit(Base):
    __tablename__ = 'audit_events'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor: Mapped[str | None] = mapped_column(String(36))
    details: Mapped[dict] = mapped_column(JSONB, default=dict, server_default='{}')
    action: Mapped[str] = mapped_column(String(64))
    resource: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
class RateBucket(Base):
    __tablename__ = 'rate_buckets'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer)
    expires: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

class SquadRecord(Base):
    __tablename__ = 'squads'
    __table_args__ = (CheckConstraint('sort_order >= 0'),)
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    country: Mapped[str] = mapped_column(String(64))
    tournament: Mapped[str] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(Integer)

class PlayerRecord(Base):
    __tablename__ = 'players'
    __table_args__ = (
        CheckConstraint('rating BETWEEN 1 AND 100'),
        CheckConstraint("role IN ('OP','BAT','AR','WK','PACE','SPIN')"),
        CheckConstraint('sort_order >= 0'),
    )
    # One record is a tournament-specific player, matching existing saved game IDs.
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    squad_id: Mapped[str] = mapped_column(ForeignKey('squads.id'), index=True)
    name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(8))
    rating: Mapped[int] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer)

class Room(Base):
    __tablename__ = 'rooms'
    visibility: Mapped[str] = mapped_column(String(7), default='private', server_default='private')
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    code: Mapped[str] = mapped_column(String(4), unique=True)
    version: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
