"""Local copies of the corpora Snowflake Cortex Search is meant to serve.

Each JSONL line is one citation: source_id, title, passage, locator.
"""

import json
import re
from pathlib import Path

from app import config

_CORPUS_DIR = Path(__file__).resolve().parents[2] / "ingest" / "corpus"
_FILES = {
    config.USPSTF_SEARCH: "uspstf.jsonl",
    config.PUBMED_SEARCH: "pubmed.jsonl",
    config.PAYER_DOCS_SEARCH: "payer_docs.jsonl",
}
_FIELDS = ("source_id", "title", "passage", "locator")
_LIMIT = 10


def corpus_file(service_name):
    name = _FILES.get(service_name)
    if name is None:
        raise ValueError(f"unknown Cortex Search service {service_name}")
    return _CORPUS_DIR / name


def load_rows(service_name):
    path = corpus_file(service_name)
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        rows.append({field: raw[field] for field in _FIELDS})
    return rows


def _terms(text):
    return [term for term in re.findall(r"[a-z0-9]+", text.lower()) if len(term) > 2]


def search_corpus(service_name, text, limit=_LIMIT):
    """Rank local passages by term overlap. Columns match a Cortex Search row."""
    terms = _terms(text)
    if not terms:
        return []
    scored = []
    for row in load_rows(service_name):
        haystack = f"{row['title']} {row['passage']}".lower()
        score = sum(haystack.count(term) for term in terms)
        if score:
            scored.append((score, row["source_id"], row))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored[:limit]]
