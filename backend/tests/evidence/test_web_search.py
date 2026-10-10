from app.evidence import web_search

from seams import DURATION_TEXT, citation_view, install_seams, redirect_uri

BLOG = "https://example.com/post"
LOOKALIKE = "https://cdc.gov.example.com/x"
CDC = "https://www.cdc.gov/colorectal-cancer/screening.htm"
GROUNDED_TEXT = (
    "Northwind Health publishes its prior authorization steps. "
    "A broken source is not cited. "
    "Screening rules are also described on a public page."
)

TITLE_BLOG = "Prior Authorization Blog"
TITLE_LOOKALIKE = "Lookalike Domain"
TITLE_FAIL = "Unresolved Source"
TITLE_CDC = "CDC Screening Page"

SEG_BLOG = "Submit the prior authorization form online."
SEG_LOOKALIKE = "A lookalike domain repeats the form steps."
SEG_FAIL = "Only the unresolved source supports this sentence."
SEG_BOTH = "Screening ages and the form are both described."
SEG_FAIL_AND_BLOG = "The unresolved source and the blog disagree."


def _chunk(slug, title):
    return {"uri": redirect_uri(slug), "title": title}


def _support(segment_text, chunk_indices):
    return {"segment_text": segment_text, "chunk_indices": chunk_indices}


def _view(title, passage, locator):
    return {
        "title": title,
        "passage": passage,
        "locator": locator,
        "tier": "web",
    }


def test_web_search_keeps_blog_and_omits_failed_redirect(monkeypatch):
    seams = install_seams(monkeypatch)
    chunks = [
        _chunk("blog", TITLE_BLOG),
        _chunk("lookalike", TITLE_LOOKALIKE),
        _chunk("fail", TITLE_FAIL),
        _chunk("cdc", TITLE_CDC),
    ]
    seams.redirects = {
        redirect_uri("blog"): BLOG,
        redirect_uri("lookalike"): LOOKALIKE,
        redirect_uri("cdc"): CDC,
    }
    seams.failing_redirects = {redirect_uri("fail")}
    seams.ground_payload = {
        "text": GROUNDED_TEXT,
        "grounding_chunks": chunks,
        "grounding_supports": [
            _support(SEG_BLOG, [0]),
            _support(SEG_LOOKALIKE, [1]),
            _support(SEG_FAIL, [2]),
            _support(SEG_BOTH, [3, 0]),
            _support(SEG_FAIL_AND_BLOG, [2, 0]),
        ],
    }

    result = web_search(DURATION_TEXT)

    assert seams.ground_calls == [DURATION_TEXT]
    assert seams.cortex_calls == []
    assert seams.redirect_calls == [chunk["uri"] for chunk in chunks]
    assert isinstance(result, dict)
    assert set(result) == {"text", "citations"}
    assert result["text"] == GROUNDED_TEXT
    assert [citation_view(citation) for citation in result["citations"]] == [
        _view(TITLE_BLOG, SEG_BLOG, BLOG),
        _view(TITLE_LOOKALIKE, SEG_LOOKALIKE, LOOKALIKE),
        _view(TITLE_CDC, SEG_BOTH, CDC),
        _view(TITLE_BLOG, SEG_BOTH, BLOG),
        _view(TITLE_BLOG, SEG_FAIL_AND_BLOG, BLOG),
    ]
    assert SEG_FAIL not in " ".join(citation["passage"] for citation in result["citations"])


def test_web_search_returns_text_and_no_citations_when_redirect_fails(monkeypatch):
    seams = install_seams(monkeypatch)
    chunks = [_chunk("fail", TITLE_FAIL)]
    seams.failing_redirects = {redirect_uri("fail")}
    seams.ground_payload = {
        "text": GROUNDED_TEXT,
        "grounding_chunks": chunks,
        "grounding_supports": [_support(SEG_FAIL, [0])],
    }

    result = web_search("Prior authorization steps for a screening colonoscopy.")

    assert seams.ground_calls == ["Prior authorization steps for a screening colonoscopy."]
    assert seams.redirect_calls == [chunks[0]["uri"]]
    assert result == {"text": GROUNDED_TEXT, "citations": []}
