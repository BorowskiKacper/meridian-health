"""Request-scoped database sessions.

Routes call get_session(). A session is bound only while a request is running
with EMR_BIND_DB=1. Tests keep supplying their own session.
"""

from contextvars import ContextVar

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config import DATABASE_URL

_current = ContextVar("emr_session", default=None)
_engine = None
_SCHEMA = "hackknight"


def get_engine():
    global _engine
    if _engine is None:
        if not str(DATABASE_URL).strip():
            raise RuntimeError("DATABASE_URL is not set.")
        _engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            connect_args={"options": f"-csearch_path={_SCHEMA},public"},
        )
    return _engine


def get_session():
    session = _current.get()
    if session is None:
        raise RuntimeError("No database session is bound.")
    return session


def bind_session(session):
    return _current.set(session)


def reset_session(token):
    _current.reset(token)


def _relax_storage(connection):
    """Let large citation passages spill out of the row.

    The models keep values inline so the test schema stays free of toast
    tables. A real eligibility check cites full payer passages and does not
    fit in that inline limit.
    """
    rows = connection.execute(
        text(
            """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND udt_name IN ('text', 'varchar', 'jsonb')
            """
        ),
        {"schema": _SCHEMA},
    ).all()
    for table, column in rows:
        connection.execute(
            text(
                f'ALTER TABLE {_SCHEMA}."{table}" '
                f'ALTER COLUMN "{column}" SET STORAGE EXTENDED'
            )
        )


def prepare_database():
    """Create the demo schema, tables, and seed patients when none are loaded."""
    import importlib.util
    from pathlib import Path

    from app.db.models import Base

    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}"))
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        connection.execute(text(f"SET search_path TO {_SCHEMA}, public"))
        Base.metadata.create_all(connection)
        _relax_storage(connection)
        count = connection.execute(text(f"SELECT count(*) FROM {_SCHEMA}.patients")).scalar()
    if count:
        return
    seed_path = Path(__file__).resolve().parents[2] / "seed" / "seed.py"
    spec = importlib.util.spec_from_file_location("emr_seed_module", seed_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    session = Session(engine)
    try:
        module.seed(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
