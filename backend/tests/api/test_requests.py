import pytest

from api_support import JANE_ID, assert_error, bind_session, call

TEXT = "Mark hypertension controlled."
REQUEST_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SPOKEN = "I drafted a chart update."


def _bound_call(args, kwargs):
    fields = dict(zip(("patient_id", "text", "channel"), args))
    fields.update(kwargs)
    return fields


def _install_speech(monkeypatch, *, transcript=None, audio_base64=None):
    transcribe_calls = []
    synthesize_calls = []

    def transcribe(self, audio):
        transcribe_calls.append(audio)
        return transcript

    def synthesize(self, text):
        synthesize_calls.append(text)
        return audio_base64

    monkeypatch.setattr(
        "app.speech.hook.SpeechHook.transcribe",
        transcribe,
        raising=False,
    )
    monkeypatch.setattr(
        "app.speech.hook.SpeechHook.synthesize",
        synthesize,
        raising=False,
    )
    return transcribe_calls, synthesize_calls


def _install_route(monkeypatch, body):
    recorded = []

    def route_doctor_request(*args, **kwargs):
        recorded.append((args, kwargs))
        return body

    monkeypatch.setattr(
        "app.agents.doctor.route_doctor_request",
        route_doctor_request,
    )
    monkeypatch.setattr(
        "app.api.routes.requests.route_doctor_request",
        route_doctor_request,
        raising=False,
    )
    return recorded


def _chart_body(**overrides):
    body = {
        "request_id": REQUEST_ID,
        "transcript": TEXT,
        "route": "chart_update",
        "suggestions": [],
        "answer": None,
        "spoken_text": None,
        "audio_base64": None,
    }
    body.update(overrides)
    return body


def test_typed_request_skips_transcription(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    transcribe_calls, _synthesize_calls = _install_speech(monkeypatch)
    expected = _chart_body()
    recorded = _install_route(monkeypatch, expected)

    response = call(
        client,
        "POST",
        "/requests",
        data={"patient_id": JANE_ID, "text": TEXT},
    )

    assert response.status_code == 200
    assert response.json() == expected
    assert transcribe_calls == []
    assert len(recorded) == 1
    fields = _bound_call(*recorded[0])
    assert fields["channel"] == "typed"
    assert fields["text"] == TEXT
    assert str(fields["patient_id"]) == JANE_ID
    assert fields["session"] is seeded_db.session


@pytest.mark.parametrize("route", ["clinical_question", "chart_update", "check_screenings"])
@pytest.mark.parametrize("voice", [False, True])
def test_explicit_workflow_reaches_doctor(seeded_db, monkeypatch, client, route, voice):
    bind_session(monkeypatch, seeded_db.session)
    _install_speech(monkeypatch, transcript=TEXT)
    recorded = _install_route(monkeypatch, _chart_body(route=route))
    data = {"patient_id": JANE_ID, "route": route}
    kwargs = {"files": {"audio": ("voice.webm", b"audio", "audio/webm")}} if voice else {}
    if not voice:
        data["text"] = TEXT
    response = call(client, "POST", "/requests", data=data, **kwargs)
    assert response.status_code == 200
    assert _bound_call(*recorded[0])["route"] == route


def test_unknown_workflow_is_rejected_before_routing(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    recorded = _install_route(monkeypatch, _chart_body())
    response = call(client, "POST", "/requests", data={"patient_id": JANE_ID, "text": TEXT, "route": "send_sms"})
    assert response.status_code == 400
    assert recorded == []


@pytest.mark.parametrize("voice", [False, True])
def test_preview_uses_read_only_mcp_tool_without_creating_requests(seeded_db, monkeypatch, client, voice):
    from sqlalchemy import select, func
    from app.db.models import Request, Suggestion
    session = seeded_db.session
    bind_session(monkeypatch, session)
    before = [session.scalar(select(func.count()).select_from(table)) for table in (Request, Suggestion)]
    calls = []
    def classify(task, payload):
        calls.append((task, payload))
        return {"route": "chart_update"}
    monkeypatch.setattr("app.agents.doctor.model.complete", classify)
    transcribed, _ = _install_speech(monkeypatch, transcript="Change weight to 70 kg")
    data = {"patient_id": JANE_ID}
    kwargs = {"files": {"audio": ("voice.webm", b"audio", "audio/webm")}} if voice else {}
    if not voice:
        data["text"] = "Change weight to 70 kg"
    response = call(client, "POST", "/requests/preview", data=data, **kwargs)
    assert response.status_code == 200
    assert response.json()["route"] == "chart_update"
    assert response.json()["transcript"] == "Change weight to 70 kg"
    assert calls == [("classify", {"text": "Change weight to 70 kg"})]
    assert bool(transcribed) == voice
    assert [session.scalar(select(func.count()).select_from(table)) for table in (Request, Suggestion)] == before


def test_confirmed_voice_uses_the_reviewed_transcript_without_retranscription(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    transcribed, _ = _install_speech(monkeypatch, transcript="Different transcript")
    recorded = _install_route(monkeypatch, _chart_body())
    response = call(client, "POST", "/requests", data={"patient_id": JANE_ID, "route": "chart_update", "reviewed_transcript": "Change weight to 70 kg"}, files={"audio": ("voice.webm", b"audio", "audio/webm")})
    assert response.status_code == 200
    assert transcribed == []
    assert _bound_call(*recorded[0])["text"] == "Change weight to 70 kg"
    assert _bound_call(*recorded[0])["channel"] == "voice"


@pytest.mark.parametrize("voice", [False, True])
def test_general_chat_has_no_patient_context_or_suggestions(seeded_db, monkeypatch, client, voice):
    bind_session(monkeypatch, seeded_db.session)
    calls = []
    def research(patient_id, text, session):
        calls.append((patient_id, text, session))
        return {"text": "Evidence answer", "citations": []}
    monkeypatch.setattr("app.agents.doctor._research_answer", research)
    _install_speech(monkeypatch, transcript="General clinical question", audio_base64="QQ==")
    kwargs = {"files": {"audio": ("voice.webm", b"audio", "audio/webm")}} if voice else {"data": {"text": "General clinical question"}}
    response = call(client, "POST", "/chat", **kwargs)
    assert response.status_code == 200
    assert calls == [(None, "General clinical question", None)]
    assert response.json()["suggestions"] == []
    assert response.json()["route"] == "clinical_question"


@pytest.mark.parametrize("extra", [{"patient_id": JANE_ID}, {"route": "chart_update"}, {"route": "check_screenings"}])
def test_general_chat_rejects_patient_scope_and_actions(client, extra):
    response = call(client, "POST", "/chat", data={"text": "Change weight to 70", **extra})
    assert response.status_code == 400


@pytest.mark.parametrize("audio_base64", [None, "QQ=="])
def test_audio_request_transcribes_and_synthesizes(
    seeded_db, monkeypatch, client, audio_base64
):
    bind_session(monkeypatch, seeded_db.session)
    transcribe_calls, synthesize_calls = _install_speech(
        monkeypatch,
        transcript=TEXT,
        audio_base64=audio_base64,
    )
    agent_body = _chart_body(spoken_text=SPOKEN, audio_base64=None)
    recorded = _install_route(monkeypatch, agent_body)

    response = call(
        client,
        "POST",
        "/requests",
        data={"patient_id": JANE_ID},
        files={"audio": ("request.webm", b"audio-bytes", "audio/webm")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["spoken_text"] == SPOKEN
    assert body["audio_base64"] == audio_base64
    assert body["transcript"] == TEXT
    assert body["route"] == "chart_update"
    assert body["request_id"] == REQUEST_ID
    assert transcribe_calls
    assert synthesize_calls == [SPOKEN]
    assert len(recorded) == 1
    fields = _bound_call(*recorded[0])
    assert fields["channel"] == "voice"
    assert fields["text"] == TEXT
    assert str(fields["patient_id"]) == JANE_ID
    assert fields["session"] is seeded_db.session


def test_audio_request_rejects_when_transcription_is_empty(monkeypatch, client):
    transcribe_calls, synthesize_calls = _install_speech(monkeypatch, transcript=None)
    recorded = _install_route(monkeypatch, _chart_body())

    response = call(
        client,
        "POST",
        "/requests",
        data={"patient_id": JANE_ID},
        files={"audio": ("request.webm", b"audio-bytes", "audio/webm")},
    )

    assert_error(response, 400, "validation_error")
    assert response.json()["error"]["message"] == "Audio could not be transcribed."
    assert recorded == []
    assert transcribe_calls == [b"audio-bytes"]
    assert synthesize_calls == []


def test_browser_preflight_allows_the_doctor_role_header(client):
    response = client.options(
        "/requests",
        headers={
            "Origin": "http://localhost:8081",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-role",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert "x-role" in response.headers["access-control-allow-headers"].lower()


@pytest.mark.parametrize(
    "data,files",
    [
        (
            {"patient_id": JANE_ID, "text": TEXT},
            {"audio": ("request.webm", b"audio-bytes", "audio/webm")},
        ),
        ({"patient_id": JANE_ID}, None),
    ],
)
def test_request_rejects_both_or_neither(seeded_db, monkeypatch, client, data, files):
    bind_session(monkeypatch, seeded_db.session)
    recorded = _install_route(monkeypatch, _chart_body())
    kwargs = {"data": data}
    if files is not None:
        kwargs["files"] = files

    response = call(client, "POST", "/requests", **kwargs)

    assert_error(response, 400, "validation_error")
    assert recorded == []
