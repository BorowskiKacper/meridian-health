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
    """Create tables, seed an empty database, and insert any missing panel charts.

    Returns whether the demo seed ran, and how many panel charts were added.
    The panel step always runs so a deploy can fill a database that already
    has the original three patients. That path skips the demo seed, so the
    body regions and reminder rules those charts reference are filled first.
    """
    engine = get_engine()
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        created = False
        if not list_patients(session):
            _seed(session)
            created = True
        _load("demo").ensure_reference(session)
        added = _load("panel").seed_panel(session)
        session.commit()
        return created, added
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo-vitals", action="store_true", help="Add labeled synthetic vital signs to the three demo patients only.")
    parser.add_argument("--panel", action="store_true", help="Add the extra fictional clinic charts when the database already has patients.")
    args = parser.parse_args()
    created, added = prepare_database()
    print("seeded" if created else "already seeded")
    if added or args.panel:
        print(f"added {added} synthetic panel charts")
    if args.demo_vitals:
        with Session(get_engine()) as session:
            added = _load("vitals").seed_vitals(session)
            session.commit()
            print(f"added {added} synthetic demo vital-sign records")
