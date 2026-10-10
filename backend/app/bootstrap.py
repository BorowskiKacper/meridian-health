"""Create the clinic tables and load the demo patients when the database is empty."""

import importlib.util
from pathlib import Path

from sqlalchemy.orm import Session

from app.runtime import get_engine
from app.db.models import Base
from app.db.repositories import list_patients

_SEED_DIR = Path(__file__).resolve().parents[1] / "seed"


def _load(name):
    path = _SEED_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"emr_{name}_module", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load seed from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _seed(session):
    base = _load("seed").seed
    return _load("demo").seed_demo(session, base)


def prepare_database():
    engine = get_engine()
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        if list_patients(session):
            return False
        _seed(session)
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    created = prepare_database()
    print("seeded" if created else "already seeded")
