from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import DATABASE_URL

_engine = None


def _database_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    return _engine


class _SessionScope:
    def __enter__(self):
        if not isinstance(DATABASE_URL, str) or not DATABASE_URL.strip():
            raise RuntimeError("DATABASE_URL is not set.")
        self._session = Session(_database_engine())
        return self._session

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self._session.commit()
            else:
                self._session.rollback()
        finally:
            self._session.close()
        return False


def open_session():
    return _SessionScope()
