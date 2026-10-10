import pytest

from app import config
from app.evidence import (
    search_guidelines,
    search_medical_web,
    search_payer_docs,
    web_search,
)

from seams import (
    ALLOWED_TEXTS,
    FORBIDDEN_TEXTS,
    PAYER_ROWS,
    USPSTF_ROWS,
    assert_passage_result,
    citation_view,
    install_seams,
    redirect_uri,
    with_tier,
)

TOOLS = [
    "search_guidelines",
    "search_medical_web",
    "search_payer_docs",
    "web_search",
]

_CDC = "https://www.cdc.gov/colorectal-cancer/screening.htm"
_BLOG = "https://example.com/post"
_SEGMENT = "Screen adults aged 45 to 75 years for colorectal cancer."
_WEB_TEXT = "Public pages describe the screening ages."


def _call(tool, text):
    if tool == "search_guidelines":
        return search_guidelines(text, "uspstf")
    if tool == "search_medical_web":
        return search_medical_web(text)
    if tool == "search_payer_docs":
        return search_payer_docs(text)
    if tool == "web_search":
        return web_search(text)
    raise AssertionError(tool)


def _arm_allowed(seams, tool):
    if tool == "search_guidelines":
        seams.cortex_rows = USPSTF_ROWS
    elif tool == "search_payer_docs":
        seams.cortex_rows = PAYER_ROWS
    elif tool == "search_medical_web":
        seams.redirects = {redirect_uri("cdc"): _CDC}
        seams.ground_payload = {
            "text": _WEB_TEXT,
            "grounding_chunks": [
                {"uri": redirect_uri("cdc"), "title": "CDC Colorectal Cancer Screening"}
            ],
            "grounding_supports": [
                {"segment_text": _SEGMENT, "chunk_indices": [0]}
            ],
        }
    elif tool == "web_search":
        seams.redirects = {redirect_uri("blog"): _BLOG}
        seams.ground_payload = {
            "text": _WEB_TEXT,
            "grounding_chunks": [
                {"uri": redirect_uri("blog"), "title": "Prior Authorization Blog"}
            ],
            "grounding_supports": [
                {"segment_text": _SEGMENT, "chunk_indices": [0]}
            ],
        }


def _assert_allowed(tool, text, seams, result):
    if tool == "search_guidelines":
        assert seams.cortex_calls == [(config.USPSTF_SEARCH, text)]
        assert seams.ground_calls == []
        assert seams.redirect_calls == []
        assert_passage_result(result, with_tier(USPSTF_ROWS, "baseline"))
    elif tool == "search_payer_docs":
        assert seams.cortex_calls == [(config.PAYER_DOCS_SEARCH, text)]
        assert seams.ground_calls == []
        assert seams.redirect_calls == []
        assert_passage_result(result, with_tier(PAYER_ROWS, "payer"))
    elif tool == "search_medical_web":
        assert seams.cortex_calls == []
        assert seams.ground_calls == [text]
        assert seams.redirect_calls == [redirect_uri("cdc")]
        assert [citation_view(passage) for passage in result["passages"]] == [
            {
                "title": "CDC Colorectal Cancer Screening",
                "passage": _SEGMENT,
                "locator": _CDC,
                "tier": "guideline",
            }
        ]
    elif tool == "web_search":
        assert seams.cortex_calls == []
        assert seams.ground_calls == [text]
        assert seams.redirect_calls == [redirect_uri("blog")]
        assert result["text"] == _WEB_TEXT
        assert [citation_view(citation) for citation in result["citations"]] == [
            {
                "title": "Prior Authorization Blog",
                "passage": _SEGMENT,
                "locator": _BLOG,
                "tier": "web",
            }
        ]


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("text", FORBIDDEN_TEXTS)
def test_identifier_raises_without_calling_seams(monkeypatch, tool, text):
    seams = install_seams(monkeypatch)
    _arm_allowed(seams, tool)

    with pytest.raises(ValueError):
        _call(tool, text)

    assert seams.cortex_calls == []
    assert seams.ground_calls == []
    assert seams.redirect_calls == []


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("text", ALLOWED_TEXTS)
def test_ages_years_and_durations_reach_the_search(monkeypatch, tool, text):
    seams = install_seams(monkeypatch)
    _arm_allowed(seams, tool)

    result = _call(tool, text)

    _assert_allowed(tool, text, seams, result)
