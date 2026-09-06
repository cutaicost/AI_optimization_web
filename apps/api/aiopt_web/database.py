from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings

class Base(DeclarativeBase):
    pass

def make_engine(url: str | None = None):
    target = url or settings().database_url
    options = {"check_same_thread": False} if target.startswith("sqlite") else {"connect_timeout":5,"keepalives_idle":5,"keepalives_interval":2,"keepalives_count":2,"tcp_user_timeout":5000}
    return create_engine(target, pool_pre_ping=True, connect_args=options)

engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
