import pytest

from support import JANE_ID, assert_error, bind_session, call

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
