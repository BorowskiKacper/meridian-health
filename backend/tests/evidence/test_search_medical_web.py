from app.evidence import search_medical_web

from seams import (
    AGE_TEXT,
    YEAR_TEXT,
    citation_view,
    install_seams,
    redirect_uri,
)

WWW_CDC = "https://www.cdc.gov/colorectal-cancer/screening.htm"
PUBMED = "https://pubmed.ncbi.nlm.nih.gov/32145678/?utm_source=grounding"
APEX_CDC = "https://cdc.gov/screening#ages"
BLOG = "https://example.com/post"
LOOKALIKE_SUB = "https://cdc.gov.example.com/x"
LOOKALIKE_NOT = "https://notcdc.gov/x"
NIH_UNUSED = "https://www.nih.gov/health-information"

TITLE_CDC = "CDC Colorectal Cancer Screening"
TITLE_PUBMED = "PubMed Family History Screening"
TITLE_APEX = "CDC Exact Host Screening"
TITLE_BLOG = "Personal Blog Post"
TITLE_SUB = "Lookalike Subdomain"
TITLE_NOT = "Lookalike Not CDC"
TITLE_FAIL = "Broken Redirect Page"
TITLE_NIH = "NIH Page With No Segment"

SEG_CDC = "Screen adults aged 45 to 75 years for colorectal cancer."
SEG_PUBMED = "A first-degree relative with colorectal cancer can justify starting earlier."
SEG_BOTH = "Average-risk screening and earlier screening for family history both apply."
SEG_BLOG = "A personal blog claims screening is unnecessary."
SEG_LOOK = "A lookalike site repeats the screening ages."
SEG_FAIL = "This redirect never resolved."
SEG_MIXED = "CDC states the screening ages and a blog disagrees."
SEG_FAIL_KEPT = "A resolved PubMed page supports the earlier start."

KEPT = [
    ("cdc-www", WWW_CDC, TITLE_CDC),
    ("pubmed", PUBMED, TITLE_PUBMED),
    ("cdc-apex", APEX_CDC, TITLE_APEX),
]
DROPPED = [
    ("blog", BLOG, TITLE_BLOG),
    ("lookalike-sub", LOOKALIKE_SUB, TITLE_SUB),
    ("lookalike-not", LOOKALIKE_NOT, TITLE_NOT),
]
FAILING = ("fail", TITLE_FAIL)
UNUSED = ("nih-unused", NIH_UNUSED, TITLE_NIH)


def _chunk(slug, title):
    return {"uri": redirect_uri(slug), "title": title}


def _support(segment_text, chunk_indices):
    return {"segment_text": segment_text, "chunk_indices": chunk_indices}


def _payload(chunks, supports, text="Grounded medical answer."):
    return {
        "text": text,
        "grounding_chunks": chunks,
        "grounding_supports": supports,
    }


def _view(title, passage, locator):
    return {
        "title": title,
        "passage": passage,
        "locator": locator,
        "tier": "guideline",
    }


def test_medical_web_keeps_allowlisted_chunks_that_back_a_segment(monkeypatch):
    seams = install_seams(monkeypatch)
    chunks = [
        _chunk(slug, title) for slug, _final, title in (*KEPT, *DROPPED)
    ]
    chunks.append(_chunk(FAILING[0], FAILING[1]))
    chunks.append(_chunk(UNUSED[0], UNUSED[2]))
    redirects = {redirect_uri(slug): final for slug, final, _title in (*KEPT, *DROPPED)}
    redirects[redirect_uri(UNUSED[0])] = UNUSED[1]
    seams.redirects = redirects
    seams.failing_redirects = {redirect_uri(FAILING[0])}
    seams.ground_payload = _payload(
        chunks,
        [
            _support(SEG_CDC, [0]),
            _support(SEG_PUBMED, [1]),
            _support(SEG_BOTH, [0, 1]),
            _support(SEG_BLOG, [3]),
            _support(SEG_LOOK, [4, 5]),
            _support(SEG_FAIL, [6]),
            _support(SEG_MIXED, [2, 3]),
            _support(SEG_FAIL_KEPT, [6, 1]),
        ],
    )
    seams.cortex_rows = [
        {
            "source_id": "should-not-be-used",
            "title": "Unused Cortex Row",
            "passage": "Cortex must not supply medical web passages.",
            "locator": "unused",
        }
    ]

    result = search_medical_web(AGE_TEXT)

    assert seams.ground_calls == [AGE_TEXT]
    assert seams.cortex_calls == []
    assert seams.redirect_calls == [chunk["uri"] for chunk in chunks]
    assert isinstance(result, dict)
    assert set(result) == {"passages"}
    assert [citation_view(passage) for passage in result["passages"]] == [
        _view(TITLE_CDC, SEG_CDC, WWW_CDC),
        _view(TITLE_PUBMED, SEG_PUBMED, PUBMED),
        _view(TITLE_CDC, SEG_BOTH, WWW_CDC),
        _view(TITLE_PUBMED, SEG_BOTH, PUBMED),
        _view(TITLE_APEX, SEG_MIXED, APEX_CDC),
        _view(TITLE_PUBMED, SEG_FAIL_KEPT, PUBMED),
    ]
    returned_text = " ".join(passage["passage"] for passage in result["passages"])
    for dropped in (SEG_BLOG, SEG_LOOK, SEG_FAIL):
        assert dropped not in returned_text
    locators = {passage["locator"] for passage in result["passages"]}
    assert BLOG not in locators
    assert LOOKALIKE_SUB not in locators
    assert LOOKALIKE_NOT not in locators
    assert NIH_UNUSED not in locators
    assert all(not locator.startswith("https://vertexaisearch.cloud.google.com/") for locator in locators)


def test_medical_web_returns_no_passages_when_every_chunk_is_dropped(monkeypatch):
    seams = install_seams(monkeypatch)
    chunks = [
        _chunk("blog", TITLE_BLOG),
        _chunk("lookalike-not", TITLE_NOT),
        _chunk("fail", TITLE_FAIL),
    ]
    seams.redirects = {
        redirect_uri("blog"): BLOG,
        redirect_uri("lookalike-not"): LOOKALIKE_NOT,
    }
    seams.failing_redirects = {redirect_uri("fail")}
    seams.ground_payload = _payload(
        chunks,
        [
            _support(SEG_BLOG, [0]),
            _support(SEG_LOOK, [1]),
            _support(SEG_FAIL, [2]),
            _support("Every backing chunk is outside the allowlist or unresolved.", [0, 1, 2]),
        ],
    )

    result = search_medical_web(YEAR_TEXT)

    assert seams.ground_calls == [YEAR_TEXT]
    assert seams.cortex_calls == []
    assert seams.redirect_calls == [chunk["uri"] for chunk in chunks]
    assert result == {"passages": []}
