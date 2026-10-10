from app import config
from app.evidence import search_payer_docs

from seams import DURATION_TEXT, PAYER_ROWS, assert_passage_result, install_seams, with_tier


def test_payer_docs_calls_configured_search_and_keeps_document_locator(monkeypatch):
    seams = install_seams(monkeypatch)
    seams.cortex_rows = PAYER_ROWS

    result = search_payer_docs(DURATION_TEXT)

    assert seams.cortex_calls == [(config.PAYER_DOCS_SEARCH, DURATION_TEXT)]
    assert seams.ground_calls == []
    assert seams.redirect_calls == []
    assert_passage_result(result, with_tier(PAYER_ROWS, "payer"))
    for passage in result["passages"]:
        assert "://" not in passage["locator"]
