import importlib.util
from pathlib import Path

import pytest

from app import config

_PATH = Path(__file__).resolve().parents[2] / "ingest" / "load_snowflake.py"
_SPEC = importlib.util.spec_from_file_location("load_snowflake", _PATH)
load_snowflake = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(load_snowflake)


def test_service_statements_create_cortex_search_on_passage():
    rows = [
        {
            "source_id": "payer:prior-authorization#1",
            "title": "Prior authorization",
            "passage": "A note's 'order' needs approval.",
            "locator": "Northwind Health, Prior authorization",
        }
    ]

    statements = load_snowflake.statements_for_service(
        config.PAYER_DOCS_SEARCH, rows, "COMPUTE_WH"
    )

    assert statements[0].startswith("CREATE OR REPLACE TABLE payer_docs_passages")
    assert "A note''s ''order'' needs approval." in statements[1]
    assert statements[2] == (
        "CREATE OR REPLACE CORTEX SEARCH SERVICE PAYER_DOCS_SEARCH "
        "ON passage "
        "ATTRIBUTES source_id, title, locator "
        'WAREHOUSE = "COMPUTE_WH" '
        "TARGET_LAG = '1 hour' "
        "AS (SELECT source_id, title, passage, locator FROM payer_docs_passages)"
    )


def test_setup_statements_quote_database_and_schema():
    assert load_snowflake.setup_statements('EMR "demo"', "evidence") == [
        'CREATE DATABASE IF NOT EXISTS "EMR ""demo"""',
        'CREATE SCHEMA IF NOT EXISTS "EMR ""demo"""."evidence"',
    ]


def test_load_refuses_blank_snowflake_settings(monkeypatch):
    for name in (
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_PAT",
        "SNOWFLAKE_DATABASE",
        "SNOWFLAKE_SCHEMA",
    ):
        monkeypatch.setattr(config, name, "")

    with pytest.raises(RuntimeError, match="SNOWFLAKE_ACCOUNT"):
        load_snowflake.load_corpora(client=object())


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = ""

    def json(self):
        return self._payload


class _Client:
    def __init__(self):
        self.calls = []

    def post(self, url, headers, json, timeout):
        self.calls.append(("post", url, headers, json, timeout))
        return _Response(
            {
                "code": "090001",
                "sqlState": "00000",
                "message": "Statement executed successfully.",
            }
        )

    def get(self, url, headers, timeout):
        raise AssertionError("a finished statement should not be polled")


def test_execute_statement_uses_programmatic_access_token():
    client = _Client()

    payload = load_snowflake.execute_statement(
        client,
        "xy12345",
        "pat-test",
        "SELECT 1",
        database="EMR",
        schema="EVIDENCE",
        warehouse="COMPUTE_WH",
    )

    method, url, headers, body, timeout = client.calls[0]
    assert method == "post"
    assert url == "https://xy12345.snowflakecomputing.com/api/v2/statements"
    assert headers["Authorization"] == "Bearer pat-test"
    assert headers["X-Snowflake-Authorization-Token-Type"] == "PROGRAMMATIC_ACCESS_TOKEN"
    assert body["statement"] == "SELECT 1"
    assert body["database"] == "EMR"
    assert body["schema"] == "EVIDENCE"
    assert body["warehouse"] == "COMPUTE_WH"
    assert payload["sqlState"] == "00000"
    assert timeout == 90.0
