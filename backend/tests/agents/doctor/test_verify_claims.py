import copy

from app.agents.doctor.verify import verify_claims

from support import baseline_citation, guideline_citation, install, literature_citation


class VerifyComplete:
    def __init__(self, handler):
        self.calls = []
        self._handler = handler

    def __call__(self, task, payload):
        self.calls.append((task, copy.deepcopy(payload)))
        assert task == "verify"
        return self._handler(payload)


def test_verify_claims_keeps_supported_sentence_and_drops_uncited(monkeypatch):
    citations = [baseline_citation(), literature_citation()]
    text = "Screening starts at 45. An unsupported claim remains."
    removed = ["An unsupported claim remains."]

    def verify(payload):
        assert payload == {"text": text, "citations": citations}
        return {
            "supported": [
                {"sentence": "Screening starts at 45.", "citation_indexes": [0]}
            ],
            "removed": removed,
        }

    model = VerifyComplete(verify)
    install(monkeypatch, model)

    result = verify_claims(text, citations)

    assert model.calls == [("verify", {"text": text, "citations": citations})]
    assert result == {
        "text": "Screening starts at 45.",
        "citations": [citations[0]],
        "removed": removed,
    }
    assert citations[1] not in result["citations"]
    assert removed[0] in result["removed"]


def test_verify_claims_joins_sentences_and_keeps_original_citation_order(monkeypatch):
    citations = [baseline_citation(), guideline_citation(), literature_citation()]

    def verify(_payload):
        return {
            "supported": [
                {
                    "sentence": "Later source applies.",
                    "citation_indexes": [2, 2, True, "1", 3, -1],
                },
                {"sentence": "Baseline still applies.", "citation_indexes": [0, 0]},
            ],
            "removed": ["Dropped claim."],
        }

    install(monkeypatch, VerifyComplete(verify))

    result = verify_claims("Original text is replaced by supported sentences.", citations)

    assert result["text"] == "Later source applies. Baseline still applies."
    assert result["citations"] == [citations[0], citations[2]]
    assert citations[1] not in result["citations"]
    assert result["removed"] == ["Dropped claim."]
