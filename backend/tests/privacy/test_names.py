import json
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel

from app import config
from app.privacy.names import (
    bind_patient_name,
    restore_prompt,
    scrub_prompt,
    submit_in_context,
)


class _Note(BaseModel):
    text: str


def _fixed_alias(_tokens, _text):
    return "Avery", "Beckett"


def test_full_name_first_name_and_last_name_are_replaced(monkeypatch):
    monkeypatch.setattr("app.privacy.names._choose_alias", _fixed_alias)
    text = "Jane Doe was seen. Jane's chart and Doe, Jane are filed. Does JaneDoe stay?"
    with bind_patient_name("Jane Doe"):
        scrubbed, alias = scrub_prompt(text)

    assert "Avery Beckett was seen." in scrubbed
    assert "Avery's chart" in scrubbed
    assert "Beckett, Avery" in scrubbed
    assert "Does JaneDoe stay?" in scrubbed
    assert restore_prompt(scrubbed, alias) == (
        "Jane Doe was seen. Jane's chart and Doe, Jane are filed. Does JaneDoe stay?"
    )


def test_case_and_comma_forms_do_not_touch_lookalike_words(monkeypatch):
    monkeypatch.setattr("app.privacy.names._choose_alias", _fixed_alias)
    text = "JANE DOE, jane doe, and Doe,Jane. Does the leeway stay?"
    with bind_patient_name("Jane Doe"):
        scrubbed, _alias = scrub_prompt(text)

    assert scrubbed.count("Avery Beckett") == 2
    assert "Beckett, Avery" in scrubbed
    assert "Does the leeway stay?" in scrubbed


def test_unbound_prompt_is_unchanged():
    assert scrub_prompt("Jane Doe") == ("Jane Doe", None)


def test_binding_ends_when_the_context_closes(monkeypatch):
    monkeypatch.setattr("app.privacy.names._choose_alias", _fixed_alias)
    with bind_patient_name("Jane Doe"):
        inside, _alias = scrub_prompt("Jane Doe")
    assert inside == "Avery Beckett"
    assert scrub_prompt("Jane Doe") == ("Jane Doe", None)


def test_empty_inner_bind_keeps_the_outer_name(monkeypatch):
    monkeypatch.setattr("app.privacy.names._choose_alias", _fixed_alias)
    with bind_patient_name("Jane Doe"):
        with bind_patient_name(None):
            scrubbed, _alias = scrub_prompt("Jane Doe")
    assert scrubbed == "Avery Beckett"


def test_json_keys_stay_when_the_name_matches_a_key(monkeypatch):
    monkeypatch.setattr("app.privacy.names._choose_alias", _fixed_alias)
    payload = '{"active": true, "note": "Active coverage for this visit"}'
    with bind_patient_name("Active"):
        scrubbed, _alias = scrub_prompt(payload)

    parsed = json.loads(scrubbed)
    assert parsed["active"] is True
    assert parsed["note"] == "Avery coverage for this visit"
    assert "Active" not in parsed["note"]


def test_plain_pool_submit_does_not_see_the_binding(monkeypatch):
    monkeypatch.setattr("app.privacy.names._choose_alias", _fixed_alias)
    seen = {}

    def read(text):
        seen["text"] = scrub_prompt(text)[0]

    with ThreadPoolExecutor(max_workers=1) as pool:
        with bind_patient_name("Jane Doe"):
            pool.submit(read, "Screen Jane Doe at 52").result()

    assert seen["text"] == "Screen Jane Doe at 52"


def test_copied_context_scrubs_inside_the_worker(monkeypatch):
    monkeypatch.setattr("app.privacy.names._choose_alias", _fixed_alias)
    seen = {}

    def read(text):
        seen["text"] = scrub_prompt(text)[0]

    with ThreadPoolExecutor(max_workers=1) as pool:
        with bind_patient_name("Jane Doe"):
            submit_in_context(pool, read, "Screen Jane Doe at 52").result()

    assert seen["text"] == "Screen Avery Beckett at 52"


class _Response:
    def __init__(self, text):
        self.text = text


class _Models:
    def __init__(self, sink, response_text):
        self.sink = sink
        self.response_text = response_text

    def generate_content(self, *, model, contents, config):
        self.sink["model"] = model
        self.sink["contents"] = contents
        self.sink["system"] = getattr(config, "system_instruction", None)
        return _Response(self.response_text)

    def embed_content(self, *, model, contents, config):
        self.sink["contents"] = contents
        self.sink["model"] = model

        class _Vector:
            values = [0.0] * 768

        class _Result:
            embeddings = [_Vector()]

        return _Result()


class _Client:
    def __init__(self, *args, **kwargs):
        sink = kwargs["http_options"]["sink"]
        self.models = _Models(sink, kwargs["http_options"]["response_text"])

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _install_client(monkeypatch, sink, response_text):
    def client(*args, **kwargs):
        options = dict(kwargs.get("http_options") or {})
        options["sink"] = sink
        options["response_text"] = response_text
        kwargs["http_options"] = options
        return _Client(*args, **kwargs)

    monkeypatch.setattr("google.genai.Client", client)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("app.privacy.names._choose_alias", _fixed_alias)


def test_gemini_json_sends_the_alias_and_restores_the_reply(monkeypatch):
    from app.integrations import gemini_json

    sink = {}
    _install_client(monkeypatch, sink, '{"text": "Avery Beckett is stable"}')
    blob = object()
    with bind_patient_name("May"):
        result = gemini_json(
            "sections may be empty",
            {"text": "May has asthma", "active": True},
            _Note,
            parts=[blob, "Note for May"],
        )

    assert result.text == "May is stable"
    sent = sink["contents"]
    assert sent[0] is blob
    assert "May" not in sent[1]
    body = json.loads(sent[2])
    assert body["text"] == "Avery has asthma"
    assert body["active"] is True
    assert sink["system"] == "sections may be empty"


def test_embed_text_sends_the_alias(monkeypatch):
    from app.integrations import embed_text

    sink = {}
    _install_client(monkeypatch, sink, "")
    with bind_patient_name("Jane Doe"):
        values = embed_text("Jane Doe LDL is 140")

    assert values == [0.0] * 768
    assert sink["contents"] == "Avery Beckett LDL is 140"


def test_eligibility_prompt_drops_the_name_and_keeps_json_keys(monkeypatch):
    from app.services.eligibility import ask_model

    sink = {}
    _install_client(
        monkeypatch,
        sink,
        '{"summary": "Avery Beckett is active", "prior_auth_required": false, "prior_auth_note": ""}',
    )
    prompt = (
        'Decide prior authorization.\n'
        '{"active": true, "order_text": "colonoscopy for Jane Doe"}'
    )
    with bind_patient_name("Jane Doe"):
        decision = ask_model(prompt)

    sent = sink["contents"]
    assert "Jane" not in sent
    assert "Doe" not in sent
    assert '"active": true' in sent
    assert "Avery Beckett" in sent
    assert decision["summary"] == "Jane Doe is active"
    assert decision["prior_auth_required"] is False


def test_grounded_search_sends_the_alias_and_restores_the_answer(monkeypatch):
    from app.evidence.grounding import grounded_search

    sink = {}
    _install_client(monkeypatch, sink, "Screen Avery Beckett at 52.")
    with bind_patient_name("Jane Doe"):
        result = grounded_search("Screen Jane Doe at 52")

    assert sink["contents"] == "Screen Avery Beckett at 52"
    assert result["text"] == "Screen Jane Doe at 52."
    assert result["grounding_chunks"] == []


def test_cortex_search_posts_the_alias(monkeypatch):
    from app.evidence.cortex import cortex_search

    captured = {}

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"results": []}

    def post(url, headers=None, json=None, timeout=None):
        captured["query"] = json["query"]
        captured["url"] = url
        return _Resp()

    monkeypatch.setattr("app.evidence.cortex.httpx.post", post)
    monkeypatch.setattr(config, "SNOWFLAKE_ACCOUNT", "example")
    monkeypatch.setattr(config, "SNOWFLAKE_DATABASE", "db")
    monkeypatch.setattr(config, "SNOWFLAKE_SCHEMA", "sch")
    monkeypatch.setattr(config, "SNOWFLAKE_PAT", "pat")
    monkeypatch.setattr("app.privacy.names._choose_alias", _fixed_alias)

    with bind_patient_name("Jane Doe"):
        rows = cortex_search("USPSTF_SEARCH", "Screen Jane Doe at age 52")

    assert rows == []
    assert captured["query"] == "Screen Avery Beckett at age 52"
    assert "Jane" not in captured["query"]


def test_guideline_search_from_a_worker_drops_the_name(monkeypatch):
    from app.evidence import search_guidelines

    captured = []

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"results": []}

    def post(url, headers=None, json=None, timeout=None):
        captured.append(json["query"])
        return _Resp()

    monkeypatch.setattr("app.evidence.cortex.httpx.post", post)
    monkeypatch.setattr(config, "SNOWFLAKE_ACCOUNT", "example")
    monkeypatch.setattr(config, "SNOWFLAKE_DATABASE", "db")
    monkeypatch.setattr(config, "SNOWFLAKE_SCHEMA", "sch")
    monkeypatch.setattr(config, "SNOWFLAKE_PAT", "pat")
    monkeypatch.setattr(config, "USPSTF_SEARCH", "USPSTF_SEARCH")
    monkeypatch.setattr("app.privacy.names._choose_alias", _fixed_alias)

    with ThreadPoolExecutor(max_workers=1) as pool:
        with bind_patient_name("Jane Doe"):
            future = submit_in_context(
                pool,
                search_guidelines,
                "Screen Jane Doe at age 52",
                "uspstf",
            )
            result = future.result()

    assert result == {"passages": []}
    assert captured == ["Screen Avery Beckett at age 52"]


def test_unbound_cortex_query_is_unchanged(monkeypatch):
    from app.evidence.cortex import cortex_search

    captured = {}

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"results": []}

    def post(url, headers=None, json=None, timeout=None):
        captured["query"] = json["query"]
        return _Resp()

    monkeypatch.setattr("app.evidence.cortex.httpx.post", post)
    monkeypatch.setattr(config, "SNOWFLAKE_ACCOUNT", "example")
    monkeypatch.setattr(config, "SNOWFLAKE_DATABASE", "db")
    monkeypatch.setattr(config, "SNOWFLAKE_SCHEMA", "sch")
    monkeypatch.setattr(config, "SNOWFLAKE_PAT", "pat")

    cortex_search("USPSTF_SEARCH", "colorectal screening at age 52")
    assert captured["query"] == "colorectal screening at age 52"


def test_eligibility_check_sends_an_alias_for_the_chart_name(seeded_db, monkeypatch):
    from app.services.eligibility import check_eligibility

    sink = {}
    _install_client(
        monkeypatch,
        sink,
        '{"summary": "Coverage is active.", "prior_auth_required": true, "prior_auth_note": "Needed for Avery Beckett"}',
    )
    queries = []

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"results": []}

    def post(url, headers=None, json=None, timeout=None):
        queries.append(json["query"])
        return _Resp()

    monkeypatch.setattr("app.evidence.cortex.httpx.post", post)
    monkeypatch.setattr(config, "SNOWFLAKE_ACCOUNT", "example")
    monkeypatch.setattr(config, "SNOWFLAKE_DATABASE", "db")
    monkeypatch.setattr(config, "SNOWFLAKE_SCHEMA", "sch")
    monkeypatch.setattr(config, "SNOWFLAKE_PAT", "pat")
    monkeypatch.setattr(config, "PAYER_DOCS_SEARCH", "PAYER_DOCS_SEARCH")

    result = check_eligibility(
        "11111111-1111-4111-8111-111111111111",
        "colonoscopy for Jane Doe",
        session=seeded_db.session,
    )

    assert "Jane" not in sink["contents"]
    assert "Doe" not in sink["contents"]
    assert "Avery Beckett" in sink["contents"]
    assert queries == ["colonoscopy for Avery Beckett"]
    assert result["summary"] == "Coverage is active."
    assert result["prior_auth"]["note"] == "Needed for Jane Doe"
    assert result["coverage"]["member_id"] == "NW-1001"
