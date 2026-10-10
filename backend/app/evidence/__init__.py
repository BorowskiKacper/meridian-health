"""Evidence search over guidelines, payer documents, and the web."""

import hashlib
from urllib.parse import urlsplit

from app import config
from app.evidence import cortex, grounding, http
from app.evidence.guard import reject_identifiers

_CITATION_FIELDS = ("source_id", "title", "passage", "locator")


def _passage(row, tier):
    citation = {field: row[field] for field in _CITATION_FIELDS}
    citation["tier"] = tier
    return citation


def _source_id(tier, locator):
    digest = hashlib.sha256(locator.encode("utf-8")).hexdigest()
    return f"{tier}:{digest[:32]}"


def _host_allowed(url, domains):
    if domains is None:
        return True
    host = urlsplit(url).hostname
    if not host:
        return False
    host = host.lower().rstrip(".")
    for domain in domains:
        allowed = domain.lower().rstrip(".")
        if host == allowed or host.endswith("." + allowed):
            return True
    return False


def _resolve_chunks(chunks, domains):
    """Resolve every chunk URI in order. None means the chunk was dropped."""
    resolved = []
    for chunk in chunks:
        try:
            final = http.resolve_redirect(chunk["uri"])
        except Exception:
            resolved.append(None)
            continue
        if not _host_allowed(final, domains):
            resolved.append(None)
            continue
        resolved.append(final)
    return resolved


def _citations_from_grounding(payload, tier, domains):
    chunks = payload["grounding_chunks"]
    resolved = _resolve_chunks(chunks, domains)
    citations = []
    for support in payload["grounding_supports"]:
        segment = support["segment_text"]
        for index in support["chunk_indices"]:
            if not isinstance(index, int) or isinstance(index, bool):
                continue
            if index < 0 or index >= len(resolved):
                continue
            locator = resolved[index]
            if locator is None:
                continue
            citations.append(
                {
                    "source_id": _source_id(tier, locator),
                    "title": chunks[index]["title"],
                    "passage": segment,
                    "locator": locator,
                    "tier": tier,
                }
            )
    return citations


def search_guidelines(text, corpus):
    """Search the USPSTF or PubMed corpus. Tiers are baseline and literature."""
    reject_identifiers(text)
    if corpus == "uspstf":
        service_name = config.USPSTF_SEARCH
        tier = "baseline"
    elif corpus == "pubmed":
        service_name = config.PUBMED_SEARCH
        tier = "literature"
    else:
        raise ValueError("corpus must be uspstf or pubmed")
    rows = cortex.cortex_search(service_name, text)
    return {"passages": [_passage(row, tier) for row in rows]}


def search_medical_web(text):
    """Grounded web search kept only when the final host is on the allowlist."""
    reject_identifiers(text)
    payload = grounding.grounded_search(text)
    passages = _citations_from_grounding(payload, "guideline", config.MEDICAL_DOMAINS)
    return {"passages": passages}


def search_payer_docs(text):
    """Search fictional payer documents. Tier is payer."""
    reject_identifiers(text)
    rows = cortex.cortex_search(config.PAYER_DOCS_SEARCH, text)
    return {"passages": [_passage(row, "payer") for row in rows]}


def web_search(text):
    """Grounded web search with no domain allowlist. Tier is web."""
    reject_identifiers(text)
    payload = grounding.grounded_search(text)
    citations = _citations_from_grounding(payload, "web", None)
    return {"text": payload["text"], "citations": citations}
