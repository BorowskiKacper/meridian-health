"""Database engine and the session bound to one HTTP request.

The clinic tables live in the ``clinic`` schema. Tests use a private schema
and never call this module, so they do not see or modify those tables.
"""

from contextvars import ContextVar

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

CLINIC_SCHEMA = "clinic"

_session: ContextVar[Session | None] = ContextVar("api_session", default=None)
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        from app.config import DATABASE_URL

        if not isinstance(DATABASE_URL, str) or not DATABASE_URL.strip():
            raise RuntimeError("DATABASE_URL is not set.")
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{CLINIC_SCHEMA}"'))
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        @event.listens_for(engine, "connect")
        def _clinic_search_path(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute(f'SET search_path TO "{CLINIC_SCHEMA}", public')
            cursor.close()

        engine.dispose()
        _engine = engine
    return _engine


def current_session():
    return _session.get()


def open_request_session():
    session = Session(get_engine())
    return _session.set(session)


def close_request_session(token, *, commit):
    session = _session.get()
    try:
        if session is not None:
            if commit:
                session.commit()
            else:
                session.rollback()
    finally:
        if session is not None:
            session.close()
        _session.reset(token)
