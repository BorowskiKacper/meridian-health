import copy
import importlib

import pytest

from app.schemas import Citation

CITATION_KEYS = {"source_id", "title", "passage", "locator", "tier"}

# Shaped from backend/ingest/corpus/uspstf.jsonl. Passages are excerpts of those rows.
USPSTF_ROWS = [
    {
        "source_id": "uspstf:colorectal-cancer-screening#1",
        "title": "USPSTF Colorectal Cancer: Screening: Recommendation Summary",
        "passage": (
            "Adults aged 50 to 75 years The USPSTF recommends screening for "
            "colorectal cancer in all adults aged 50 to 75 years."
        ),
        "locator": (
            "https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/"
            "colorectal-cancer-screening"
        ),
    },
    {
        "source_id": "uspstf:colorectal-cancer-screening#2",
        "title": "USPSTF Colorectal Cancer: Screening: Clinician Summary",
        "passage": (
            "For adults aged 45 to 49 years:Screen adults aged 45 to 49 years "
            "for colorectal cancer. Grade B"
        ),
        "locator": (
            "https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/"
            "colorectal-cancer-screening"
        ),
    },
]

# No pubmed.jsonl is in the corpus. Same fields as a Cortex passage.
PUBMED_ROWS = [
    {
        "source_id": "pubmed:32145678",
        "title": "Family history and the age to start colorectal cancer screening",
        "passage": (
            "Adults with a first-degree relative diagnosed with colorectal cancer "
            "are often screened earlier than the average-risk start age."
        ),
        "locator": "https://pubmed.ncbi.nlm.nih.gov/32145678/",
    }
]

# Shaped from backend/ingest/corpus/payer_docs.jsonl. Locators are document names.
PAYER_ROWS = [
    {
        "source_id": "payer:claims-and-appeals#1",
        "title": "Northwind Health Claims and Appeals Guide",
        "passage": (
            "Fictional insurer for a hackathon demo. Northwind Health is not a "
            "real company and this is not a real coverage policy."
        ),
        "locator": "Northwind Health, Northwind Health Claims and Appeals Guide",
    },
    {
        "source_id": "payer:claims-and-appeals#2",
        "title": "Northwind Health Claims and Appeals Guide: Claim submission",
        "passage": (
            "In-network providers submit claims electronically within 180 days "
            "of the date of service. Claims submitted after 180 days are denied "
            "for timely filing, and the member may not be billed for them."
        ),
        "locator": "Northwind Health, Northwind Health Claims and Appeals Guide",
    },
]

AGE_TEXT = "Colorectal cancer screening for a 52-year-old adult at average risk."
YEAR_TEXT = "Symptoms have continued since 2019."
DURATION_TEXT = "The cough has lasted for 6 weeks."
ALLOWED_TEXTS = [AGE_TEXT, YEAR_TEXT, DURATION_TEXT]

FORBIDDEN_TEXTS = [
    "Screening note 11111111-1111-4111-8111-111111111111 for this visit.",
    "Screening note a1b2c3d4-e5f6-4789-a012-3456789abcde for this visit.",
    "Check member NW-1001 before the screening.",
    "Check member NW-7 before the screening.",
    "Call +15555550101 about the screening result.",
    "Seen on 2026-09-01 for screening.",
    "Seen on 09/01/2026 for screening.",
    "Seen on Sept 1, 2026 for screening.",
    "52-year-old adult seen on 2026-09-01.",
]


def redirect_uri(slug):
    return f"https://vertexaisearch.cloud.google.com/grounding-api-redirect/{slug}"


def load_seam(module_name):
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        pytest.fail(f"{module_name} is missing: {exc}")


class Seams:
    """Replacements for the evidence network seams. Nothing here contacts a vendor."""

    def __init__(self):
        self.cortex_calls = []
        self.ground_calls = []
        self.redirect_calls = []
        self.cortex_rows = []
        self.ground_payload = {
            "text": "",
            "grounding_chunks": [],
            "grounding_supports": [],
        }
        self.redirects = {}
        self.failing_redirects = set()

    def cortex_search(self, service_name, text):
        self.cortex_calls.append((service_name, text))
        return [dict(row) for row in self.cortex_rows]

    def grounded_search(self, text):
        self.ground_calls.append(text)
        return copy.deepcopy(self.ground_payload)

    def resolve_redirect(self, url):
        self.redirect_calls.append(url)
        if url in self.failing_redirects:
            raise RuntimeError("redirect failed")
        return self.redirects.get(url, url)


def install_seams(monkeypatch):
    seams = Seams()
    cortex = load_seam("app.evidence.cortex")
    grounding = load_seam("app.evidence.grounding")
    http = load_seam("app.evidence.http")
    for module, name, fn in (
        (cortex, "cortex_search", seams.cortex_search),
        (grounding, "grounded_search", seams.grounded_search),
        (http, "resolve_redirect", seams.resolve_redirect),
    ):
        if not hasattr(module, name):
            pytest.fail(f"{module.__name__}.{name} is missing")
        monkeypatch.setattr(module, name, fn)
    return seams


def assert_citation(citation):
    assert isinstance(citation, dict)
    assert set(citation) == CITATION_KEYS
    Citation.model_validate(citation)
    return citation


def assert_passage_result(result, expected):
    assert isinstance(result, dict)
    assert set(result) == {"passages"}
    assert isinstance(result["passages"], list)
    assert result["passages"] == expected
    for passage in result["passages"]:
        assert_citation(passage)


def citation_view(citation):
    checked = assert_citation(citation)
    return {
        "title": checked["title"],
        "passage": checked["passage"],
        "locator": checked["locator"],
        "tier": checked["tier"],
    }


def with_tier(rows, tier):
    return [{**row, "tier": tier} for row in rows]
