from collections.abc import Generator
from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import get_settings

_engine: Engine | None = None
_engine_url: str | None = None
_SessionLocal = None
_lock = Lock()


def get_engine() -> Engine:
    """Create the SQLAlchemy engine lazily from the current project .env.

    Older builds created the engine at import time. When users edited .env or
    extracted an update while uvicorn --reload was running, the app could keep
    using a stale URL such as localhost,1433. This lazy builder always uses the
    currently resolved settings and rebuilds the engine if the URL changes.
    """
    global _engine, _engine_url, _SessionLocal
    settings = get_settings()
    url = settings.sqlalchemy_database_url

    with _lock:
        if _engine is None or _engine_url != url:
            if _engine is not None:
                _engine.dispose()
            _engine = create_engine(
                url,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
                future=True,
            )
            _engine_url = url
            _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine


class Base(DeclarativeBase):
    pass


def get_db() -> Generator:
    # Force engine creation from current settings right before the request needs DB.
    get_engine()
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
