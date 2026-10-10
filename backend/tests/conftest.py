import importlib.util
import re
import secrets
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

DB_TEST_DIR = Path(__file__).resolve().parent / "db"
if str(DB_TEST_DIR) not in sys.path:
    sys.path.insert(0, str(DB_TEST_DIR))

from app.config import DATABASE_URL

_SCHEMA_NAME = re.compile(r"test_[0-9a-f]{32}")
_SEED = None


class SeededDB:
    def __init__(self, session, patient_ids):
        self.session = session
        self.patient_ids = patient_ids


def _load_seed():
    global _SEED
    if _SEED is not None:
        return _SEED
    path = BACKEND_DIR / "seed" / "seed.py"
    spec = importlib.util.spec_from_file_location("emr_seed_module", path)
    if spec is None or spec.loader is None:
        pytest.fail(f"could not load seed from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _SEED = module.seed
    return _SEED


def _open_database():
    if not isinstance(DATABASE_URL, str) or not DATABASE_URL.strip():
        pytest.fail("DATABASE_URL is not set")
    database_engine = None
    try:
        database_engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        with database_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        if database_engine is not None:
            database_engine.dispose()
        raise pytest.fail.Exception("DATABASE_URL connection failed") from None
    return database_engine


def _bind_search_path(database_engine, schema):
    def set_search_path(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        # public stays later on the path so the existing vector type resolves.
        cursor.execute(f'SET search_path TO "{schema}", public')
        cursor.close()

    event.listen(database_engine, "connect", set_search_path)
    return set_search_path


def _reject_foreign_schema(base, schema):
    if base.metadata.schema not in (None, schema):
        pytest.fail("refusing to create tables outside the test schema")
    for table in base.metadata.tables.values():
        if table.schema not in (None, schema):
            pytest.fail("refusing to create tables outside the test schema")


def _object_snapshot(connection, schema):
    relations = connection.execute(
        text(
            """
            SELECT n.nspname, c.relname, c.relkind
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname <> :schema
              AND n.nspname NOT IN ('pg_catalog', 'information_schema')
              AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f', 'i')
            """
        ),
        {"schema": schema},
    ).all()
    types = connection.execute(
        text(
            """
            SELECT n.nspname, t.typname
            FROM pg_type t
            JOIN pg_namespace n ON n.oid = t.typnamespace
            WHERE n.nspname <> :schema
              AND n.nspname NOT IN ('pg_catalog', 'information_schema')
              AND t.typtype IN ('e', 'c', 'd')
            """
        ),
        {"schema": schema},
    ).all()
    return (frozenset(relations), frozenset(types))


@pytest.fixture(scope="session")
def engine():
    database_engine = _open_database()
    schema = f"test_{secrets.token_hex(16)}"
    if _SCHEMA_NAME.fullmatch(schema) is None:
        database_engine.dispose()
        raise RuntimeError("refusing unexpected test schema name")
    # Qualify ORM tables so create_all's existence checks cannot reuse public
    # application tables when testing an already-populated database.
    database_engine = database_engine.execution_options(schema_translate_map={None: schema})
    try:
        from app.db.models import Base
    except Exception:
        database_engine.dispose()
        raise

    listener = None
    try:
        with database_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        listener = _bind_search_path(database_engine, schema)
        database_engine.dispose()
        _reject_foreign_schema(Base, schema)
        with database_engine.connect() as connection:
            before = _object_snapshot(connection, schema)
        with database_engine.begin() as connection:
            connection.execute(text(f'SET search_path TO "{schema}", public'))
            Base.metadata.create_all(connection)
        with database_engine.connect() as connection:
            after = _object_snapshot(connection, schema)
        if after != before:
            pytest.fail("table creation changed a schema other than the test schema")
        yield database_engine
    finally:
        if listener is not None:
            event.remove(database_engine, "connect", listener)
        with database_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        database_engine.dispose()


@pytest.fixture
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def seed_fn():
    return _load_seed()


@pytest.fixture
def seeded_db(db):
    patient_ids = _load_seed()(db)
    return SeededDB(db, patient_ids)
