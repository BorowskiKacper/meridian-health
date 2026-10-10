import httpx
import pytest

from app import config
from app.evidence import cortex


def _blank_snowflake(monkeypatch):
    for name in (
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_PAT",
        "SNOWFLAKE_DATABASE",
        "SNOWFLAKE_SCHEMA",
    ):
        monkeypatch.setattr(config, name, "")


def test_blank_settings_search_local_payer_docs_without_http(monkeypatch):
    _blank_snowflake(monkeypatch)

    def fail_post(*args, **kwargs):
        raise AssertionError("Snowflake REST should not be called without settings")

    monkeypatch.setattr(httpx, "post", fail_post)

    rows = cortex.cortex_search(config.PAYER_DOCS_SEARCH, "prior authorization claims")

    assert rows
    assert rows[0]["source_id"].startswith("payer:")
    assert set(rows[0]) == {"source_id", "title", "passage", "locator"}


def test_blank_settings_rank_uspstf_colorectal_passages(monkeypatch):
    _blank_snowflake(monkeypatch)

    rows = cortex.cortex_search(
        config.USPSTF_SEARCH,
        "Colorectal cancer screening for a 52-year-old adult at average risk.",
    )

    assert rows
    assert rows[0]["source_id"].startswith("uspstf:colorectal-cancer-screening")
    assert "colorectal" in rows[0]["passage"].lower()


def test_missing_pubmed_corpus_returns_no_rows(monkeypatch):
    _blank_snowflake(monkeypatch)

    assert cortex.cortex_search(config.PUBMED_SEARCH, "colorectal cancer screening") == []


def test_unknown_service_is_rejected_when_settings_are_blank(monkeypatch):
    _blank_snowflake(monkeypatch)

    with pytest.raises(ValueError):
        cortex.cortex_search("OTHER_SEARCH", "screening")


def test_configured_account_posts_cortex_query(monkeypatch):
    monkeypatch.setattr(config, "SNOWFLAKE_ACCOUNT", "xy12345.us-east-1")
    monkeypatch.setattr(config, "SNOWFLAKE_PAT", "pat-test")
    monkeypatch.setattr(config, "SNOWFLAKE_DATABASE", "EMR")
    monkeypatch.setattr(config, "SNOWFLAKE_SCHEMA", "EVIDENCE")
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [
                    {
                        "source_id": "uspstf:colorectal-cancer-screening#1",
                        "title": "USPSTF Colorectal Cancer: Screening",
                        "passage": "Screen adults aged 45 to 75 years.",
                        "locator": "https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/colorectal-cancer-screening",
                    }
                ]
            }

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(httpx, "post", fake_post)

    rows = cortex.cortex_search(config.USPSTF_SEARCH, "colorectal screening")

    assert captured["url"] == (
        "https://xy12345.us-east-1.snowflakecomputing.com/api/v2/databases/EMR"
        "/schemas/EVIDENCE/cortex-search-services/USPSTF_SEARCH:query"
    )
    assert captured["headers"]["Authorization"] == "Bearer pat-test"
    assert captured["headers"]["X-Snowflake-Authorization-Token-Type"] == (
        "PROGRAMMATIC_ACCESS_TOKEN"
    )
    assert captured["json"] == {
        "query": "colorectal screening",
        "columns": ["source_id", "title", "passage", "locator"],
        "limit": 10,
    }
    assert rows[0]["source_id"] == "uspstf:colorectal-cancer-screening#1"
