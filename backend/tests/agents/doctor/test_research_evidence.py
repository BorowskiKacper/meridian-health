from app.agents.doctor.model import Research, SearchQuery, Verification, complete


def test_research_searches_the_open_web_and_keeps_those_passages(monkeypatch):
    web = {
        "source_id": "web:psyllium",
        "title": "MedlinePlus psyllium",
        "passage": "Psyllium can cause bloating.",
        "locator": "https://medlineplus.gov/druginfo/natural/866.html",
        "tier": "web",
    }
    calls = {"web": [], "medical": [], "guidelines": []}

    def search_research_web(text):
        calls["web"].append(text)
        return {"passages": [web]}

    def search_medical_web(text):
        calls["medical"].append(text)
        raise AssertionError("research must not use the allowlisted web search")

    def search_guidelines(text, corpus):
        calls["guidelines"].append((text, corpus))
        return {"passages": []}

    def gemini_json(instruction, payload, schema, *, parts=None):
        if schema is SearchQuery:
            return SearchQuery(query="psyllium benefits harms")
        if schema is Research:
            assert "open-web passages" in instruction
            assert payload["evidence"] == [web]
            return Research(
                answer={"text": web["passage"], "citations": [web], "sections": []},
                recommends_action=True,
            )
        raise AssertionError(schema.__name__)

    monkeypatch.setattr("app.evidence.search_research_web", search_research_web)
    monkeypatch.setattr("app.evidence.search_medical_web", search_medical_web)
    monkeypatch.setattr("app.evidence.search_guidelines", search_guidelines)
    monkeypatch.setattr("app.agents.doctor.model.gemini_json", gemini_json)

    result = complete(
        "research",
        {"text": "Find the benefits and disadvantages of psyllium", "context": {}, "notes": {}},
    )

    assert calls["web"] == ["psyllium benefits harms"]
    assert calls["medical"] == []
    assert {corpus for _text, corpus in calls["guidelines"]} == {"uspstf", "pubmed"}
    assert result["recommends_action"] is True
    assert result["answer"]["citations"] == [web]
    assert result["answer"]["text"] == web["passage"]


def test_verify_accepts_any_cited_tier_for_research_and_not_for_reminders(monkeypatch):
    seen = []

    def gemini_json(instruction, payload, schema, *, parts=None):
        seen.append(instruction)
        return Verification(supported=[], removed=[])

    monkeypatch.setattr("app.agents.doctor.model.gemini_json", gemini_json)

    complete("verify", {"text": "Psyllium can cause bloating.", "citations": [], "allow_any_tier": True})
    complete("verify", {"text": "Start screening at 45.", "citations": []})

    assert "including literature and web sources" in seen[0]
    assert "baseline/guideline" not in seen[0]
    assert "Chart-specific facts require chart evidence." in seen[0]
    assert "Medical recommendations require baseline/guideline evidence." in seen[1]
    assert "Chart-specific facts require chart evidence." in seen[1]
