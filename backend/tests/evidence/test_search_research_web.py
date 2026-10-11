from app.evidence import search_research_web

from seams import AGE_TEXT, citation_view, install_seams, redirect_uri

BLOG = "https://medlineplus.gov/druginfo/natural/866.html"
CDC = "https://www.cdc.gov/cholesterol/treatment.htm"
TITLE_BLOG = "MedlinePlus Psyllium"
TITLE_CDC = "CDC Cholesterol Treatment"
TITLE_FAIL = "Broken Redirect Page"
SEG_BLOG = "Psyllium can cause bloating and may reduce absorption of other medicines."
SEG_CDC = "Soluble fiber can lower LDL cholesterol."
SEG_FAIL = "This redirect never resolved."
SEG_BOTH = "Fiber supplements have both lipid and gastrointestinal effects."


def _chunk(slug, title):
    return {"uri": redirect_uri(slug), "title": title}


def _support(segment_text, chunk_indices):
    return {"segment_text": segment_text, "chunk_indices": chunk_indices}


def _view(title, passage, locator):
    return {"title": title, "passage": passage, "locator": locator, "tier": "web"}


def test_research_web_keeps_resolved_pages_outside_the_medical_allowlist(monkeypatch):
    seams = install_seams(monkeypatch)
    chunks = [
        _chunk("medlineplus", TITLE_BLOG),
        _chunk("cdc", TITLE_CDC),
        _chunk("fail", TITLE_FAIL),
    ]
    seams.redirects = {
        redirect_uri("medlineplus"): BLOG,
        redirect_uri("cdc"): CDC,
    }
    seams.failing_redirects = {redirect_uri("fail")}
    seams.ground_payload = {
        "text": "Grounded answer.",
        "grounding_chunks": chunks,
        "grounding_supports": [
            _support(SEG_BLOG, [0]),
            _support(SEG_CDC, [1]),
            _support(SEG_FAIL, [2]),
            _support(SEG_BOTH, [0, 1]),
        ],
    }

    result = search_research_web(AGE_TEXT)

    assert seams.ground_calls == [AGE_TEXT]
    assert seams.cortex_calls == []
    assert result["passages"]
    assert [citation_view(passage) for passage in result["passages"]] == [
        _view(TITLE_BLOG, SEG_BLOG, BLOG),
        _view(TITLE_CDC, SEG_CDC, CDC),
        _view(TITLE_BLOG, SEG_BOTH, BLOG),
        _view(TITLE_CDC, SEG_BOTH, CDC),
    ]
    assert SEG_FAIL not in " ".join(passage["passage"] for passage in result["passages"])
