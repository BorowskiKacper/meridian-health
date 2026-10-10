import pytest

from app import config
from app.evidence import search_guidelines

from seams import AGE_TEXT, PUBMED_ROWS, USPSTF_ROWS, YEAR_TEXT, assert_passage_result, install_seams, with_tier


def test_uspstf_calls_configured_search_and_marks_baseline(monkeypatch):
    seams = install_seams(monkeypatch)
    seams.cortex_rows = USPSTF_ROWS

    result = search_guidelines(AGE_TEXT, "uspstf")

    assert seams.cortex_calls == [(config.USPSTF_SEARCH, AGE_TEXT)]
    assert seams.ground_calls == []
    assert seams.redirect_calls == []
    assert_passage_result(result, with_tier(USPSTF_ROWS, "baseline"))


def test_pubmed_calls_configured_search_and_marks_literature(monkeypatch):
    seams = install_seams(monkeypatch)
    seams.cortex_rows = PUBMED_ROWS

    result = search_guidelines(YEAR_TEXT, "pubmed")

    assert seams.cortex_calls == [(config.PUBMED_SEARCH, YEAR_TEXT)]
    assert seams.ground_calls == []
    assert seams.redirect_calls == []
    assert_passage_result(result, with_tier(PUBMED_ROWS, "literature"))


@pytest.mark.parametrize("corpus", ["payer", "PubMed", "USPSTF", "", "web"])
def test_other_corpus_raises_without_searching(monkeypatch, corpus):
    seams = install_seams(monkeypatch)
    seams.cortex_rows = USPSTF_ROWS

    with pytest.raises(ValueError):
        search_guidelines(AGE_TEXT, corpus)

    assert seams.cortex_calls == []
    assert seams.ground_calls == []
    assert seams.redirect_calls == []
