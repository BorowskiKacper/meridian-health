"""Config constants, empty environment defaults, and backend/.env.example."""

import importlib
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"

ENV_NAMES = (
    "DATABASE_URL",
    "GEMINI_API_KEY",
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_PAT",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_SCHEMA",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_FROM_NUMBER",
    "ELEVENLABS_API_KEY",
)

MEDICAL_DOMAINS = {
    "uspreventiveservicestaskforce.org",
    "cdc.gov",
    "nih.gov",
    "cancer.gov",
    "fda.gov",
    "cancer.org",
    "heart.org",
    "ahajournals.org",
    "acc.org",
    "diabetesjournals.org",
    "gastro.org",
    "gi.org",
    "asge.org",
    "acog.org",
    "auanet.org",
    "aafp.org",
    "acponline.org",
    "cochranelibrary.com",
    "who.int",
    "nice.org.uk",
}

ENV_ASSIGNMENT = re.compile(
    r"^(?:export\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>.*)$"
)


def unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def test_config_constants_and_setting_names():
    try:
        config = importlib.import_module("app.config")
    except Exception as exc:
        pytest.fail(f"import app.config failed: {exc.__class__.__name__}: {exc}")

    assert config.GEMINI_MODEL == "gemini-3.6-flash"
    assert config.EMBEDDING_MODEL == "gemini-embedding-001"
    assert config.EMBEDDING_DIMENSION == 768
    assert config.USPSTF_SEARCH == "USPSTF_SEARCH"
    assert config.PUBMED_SEARCH == "PUBMED_SEARCH"
    assert config.PAYER_DOCS_SEARCH == "PAYER_DOCS_SEARCH"
    assert set(config.MEDICAL_DOMAINS) == MEDICAL_DOMAINS

    for name in ENV_NAMES:
        assert hasattr(config, name), f"app.config.{name} is missing"
        value = getattr(config, name)
        assert isinstance(value, str), f"app.config.{name} must be a string"


def test_config_imports_when_environment_is_unset(tmp_path):
    env = os.environ.copy()
    for name in ENV_NAMES:
        env.pop(name, None)
    env["PYTHONPATH"] = str(BACKEND_DIR)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", "import app.config"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_env_example_lists_empty_values():
    path = BACKEND_DIR / ".env.example"
    if not path.is_file():
        pytest.fail("backend/.env.example is missing")
    text = path.read_text(encoding="utf-8").lstrip("\ufeff")
    values = {}
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = ENV_ASSIGNMENT.match(line)
        assert match, f"backend/.env.example:{line_no} is not an assignment"
        values[match.group("name")] = unquote(match.group("value").strip())

    missing = [name for name in ENV_NAMES if name not in values]
    assert not missing, f"backend/.env.example is missing {missing}"
    nonempty = {name: value for name, value in values.items() if value != ""}
    assert not nonempty, f"backend/.env.example values must be empty, found {nonempty}"
