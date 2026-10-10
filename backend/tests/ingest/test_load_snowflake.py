import json
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import config
from backend.ingest.load_snowflake import load_rows, main

ROWS = [
    {
        "source_id": "uspstf:colorectal#1",
        "title": "Colorectal screening",
        "passage": "Start at 45.",
        "locator": "https://www.uspreventiveservicestaskforce.org/example",
    },
    {
        "source_id": "uspstf:colorectal#2",
        "title": "Family history",
        "passage": "Earlier when a first-degree relative was diagnosed.",
        "locator": "https://www.uspreventiveservicestaskforce.org/example-2",
    },
    {
        "source_id": "uspstf:colorectal#3",
        "title": "Interval",
        "passage": "Repeat on the schedule in the passage.",
        "locator": "https://www.uspreventiveservicestaskforce.org/example-3",
    },
]


def _settings(monkeypatch, account="xy12345"):
    monkeypatch.setattr(config, "SNOWFLAKE_ACCOUNT", account)
    monkeypatch.setattr(config, "SNOWFLAKE_PAT", "pat-token")
    monkeypatch.setattr(config, "SNOWFLAKE_DATABASE", "EMR")
    monkeypatch.setattr(config, "SNOWFLAKE_SCHEMA", "PUBLIC")


def test_load_rows_posts_each_service(monkeypatch):
    _settings(monkeypatch)
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return type("Response", (), {"status_code": 200})()

    for service in ("USPSTF_SEARCH", "PUBMED_SEARCH", "PAYER_DOCS_SEARCH"):
        load_rows(service, ROWS, post)

    assert len(calls) == 3
    for (url, kwargs), service in zip(calls, ("USPSTF_SEARCH", "PUBMED_SEARCH", "PAYER_DOCS_SEARCH")):
        assert url.startswith("https://xy12345.snowflakecomputing.com/")
        assert "/databases/EMR/" in url
        assert "/schemas/PUBLIC/" in url
        assert service in url
        headers = kwargs["headers"]
        assert headers["Authorization"] == "Bearer pat-token"
        assert headers["X-Snowflake-Authorization-Token-Type"] == "PROGRAMMATIC_ACCESS_TOKEN"
        assert headers["Accept"] == "application/json"
        assert headers["Content-Type"] == "application/json"
        blob = json.dumps(kwargs["json"])
        for row in ROWS:
            for field in ("source_id", "title", "passage", "locator"):
                assert row[field] in blob
        assert "patient_id" not in blob


def test_account_host_strips_scheme_and_suffix(monkeypatch):
    _settings(monkeypatch, account="https://xy12345.snowflakecomputing.com/")
    calls = []

    def post(url, **kwargs):
        calls.append(url)

    load_rows("USPSTF_SEARCH", ROWS[:1], post)
    assert calls[0].startswith("https://xy12345.snowflakecomputing.com/")


def test_main_reads_temporary_corpora_and_names_a_missing_file(monkeypatch, tmp_path):
    _settings(monkeypatch)
    corpus = {}
    for service in ("USPSTF_SEARCH", "PUBMED_SEARCH", "PAYER_DOCS_SEARCH"):
        path = tmp_path / f"{service}.jsonl"
        path.write_text("\n".join(json.dumps(row) for row in ROWS) + "\n")
        corpus[service] = path
    monkeypatch.setattr("backend.ingest.load_snowflake.CORPUS", corpus)
    calls = []

    def post(url, **kwargs):
        calls.append(kwargs["json"])

    monkeypatch.setattr(httpx, "post", post)
    main()
    assert len(calls) == 3

    missing = tmp_path / "missing.jsonl"
    monkeypatch.setattr(
        "backend.ingest.load_snowflake.CORPUS",
        {"USPSTF_SEARCH": missing},
    )
    with pytest.raises(FileNotFoundError, match="missing.jsonl"):
        main()


def test_app_does_not_import_the_loader():
    app = ROOT / "backend" / "app"
    for path in app.rglob("*.py"):
        assert "load_snowflake" not in path.read_text(encoding="utf-8")
