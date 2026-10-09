"""The skeleton modules exist and import."""

import importlib
import importlib.util
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]

MODULES = [
    "app.config",
    "app.schemas",
    "app.db.models",
    "app.db.repositories",
    "app.main",
    "app.api.routes.body",
    "app.api.routes.requests",
    "app.api.routes.suggestions",
    "app.api.routes.documents",
    "app.api.routes.reminders",
    "app.api.routes.eligibility",
    "app.api.routes.appointments",
    "app.api.routes.secretary",
    "app.api.routes.webhooks",
    "app.mcp.tools",
    "app.agents.doctor",
    "app.agents.doctor.verify",
    "app.agents.secretary",
    "app.services.chart",
    "app.services.appointments",
    "app.services.eligibility",
    "app.services.reminders",
    "app.services.sms",
    "app.services.approval",
    "app.services.labs",
    "app.evidence",
    "app.speech.hook",
]

PACKAGES = {"app.schemas", "app.db.repositories"}


def load_seed_module():
    seed_path = BACKEND_DIR / "seed" / "seed.py"
    if not seed_path.is_file():
        pytest.fail(f"missing {seed_path}")
    spec = importlib.util.spec_from_file_location("seed", seed_path)
    if spec is None or spec.loader is None:
        pytest.fail(f"could not load {seed_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("module_name", MODULES)
def test_module_imports(module_name):
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        pytest.fail(f"import {module_name} failed: {exc.__class__.__name__}: {exc}")
    if module_name in PACKAGES:
        assert getattr(module, "__path__", None), f"{module_name} must be a package"


def test_seed_module_exposes_callable_seed():
    module = load_seed_module()
    seed = getattr(module, "seed", None)
    assert callable(seed), "backend/seed/seed.py must expose a callable seed"
