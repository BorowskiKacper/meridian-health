import struct
import zlib

import httpx
import pytest
from google import genai
from google.genai import types
from twilio.rest import Client
from twilio.rest.api.v2010.account.message import MessageList

from app import config
from app.evidence.cortex import cortex_search
from app.evidence.grounding import grounded_search
from app.services.eligibility import ask_model

_ELEVENLABS = "https://api.elevenlabs.io/v1"
_QUERY = "colorectal cancer screening"
_SPOKEN = "Hello."


def _require(name):
    value = getattr(config, name)
    if not isinstance(value, str) or not value.strip():
        pytest.fail(f"{name} is not set")
    return value


def _png_1x1():
    def chunk(tag, data):
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    raw = b"\x00\xff\x00\x00"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _gemini():
    return genai.Client(api_key=_require("GEMINI_API_KEY"), http_options={"timeout": 90000, "retry_options": {"attempts": 1}})


def _elevenlabs(method, path, **kwargs):
    key = _require("ELEVENLABS_API_KEY")
    headers = {"xi-api-key": key}
    headers.update(kwargs.pop("headers", {}))
    response = httpx.request(
        method,
        _ELEVENLABS + path,
        headers=headers,
        timeout=30.0,
        **kwargs,
    )
    if response.status_code != 200:
        detail = response.text[:200].replace(key, "")
        pytest.fail(
            f"ElevenLabs {method} {path} returned {response.status_code}: {detail}"
        )
    return response


def test_gemini_key_returns_an_eligibility_decision():
    _require("GEMINI_API_KEY")
    decision = ask_model(
        "Plan Northwind is active and covers screening colonoscopy. "
        "Reply with summary, prior_auth_required, and prior_auth_note."
    )

    assert set(decision) == {"summary", "prior_auth_required", "prior_auth_note"}
    assert isinstance(decision["summary"], str) and decision["summary"].strip()
    assert isinstance(decision["prior_auth_required"], bool)
    assert isinstance(decision["prior_auth_note"], str)


def test_gemini_key_embeds_text_at_the_configured_dimension():
    client = _gemini()
    response = client.models.embed_content(
        model=config.EMBEDDING_MODEL,
        contents=_QUERY,
        config={"output_dimensionality": config.EMBEDDING_DIMENSION},
    )

    values = response.embeddings[0].values
    assert len(values) == config.EMBEDDING_DIMENSION
    assert all(type(value) is float for value in values)


def test_gemini_key_reads_an_image():
    client = _gemini()
    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=_png_1x1(), mime_type="image/png"),
            "Reply with one word.",
        ],
    )

    assert isinstance(response.text, str) and response.text.strip()


def test_gemini_key_runs_a_grounded_search():
    _require("GEMINI_API_KEY")
    result = grounded_search("USPSTF colorectal cancer screening recommendation")

    assert isinstance(result["text"], str) and result["text"].strip()
    assert result["grounding_chunks"]
    for chunk in result["grounding_chunks"]:
        assert isinstance(chunk["uri"], str) and chunk["uri"]
        assert isinstance(chunk["title"], str)
    assert isinstance(result["grounding_supports"], list)


@pytest.mark.parametrize(
    "service_name",
    [config.USPSTF_SEARCH, config.PUBMED_SEARCH, config.PAYER_DOCS_SEARCH],
)
def test_snowflake_pat_queries_cortex_search(service_name):
    _require("SNOWFLAKE_PAT")
    _require("SNOWFLAKE_ACCOUNT")
    _require("SNOWFLAKE_DATABASE")
    _require("SNOWFLAKE_SCHEMA")

    rows = cortex_search(service_name, _QUERY)

    assert rows
    for row in rows:
        assert set(row) == {"source_id", "title", "passage", "locator"}
        assert all(isinstance(row[key], str) and row[key] for key in row)


def test_twilio_credentials_read_the_account_without_sending(monkeypatch):
    def create(*args, **kwargs):
        raise AssertionError("messages.create was called")

    monkeypatch.setattr(MessageList, "create", create)
    sid = _require("TWILIO_ACCOUNT_SID")
    client = Client(sid, _require("TWILIO_AUTH_TOKEN"))

    account = client.api.accounts(sid).fetch()
    messages = client.messages.list(limit=1)

    assert account.sid == sid
    assert account.status == "active"
    assert isinstance(messages, list)


def test_elevenlabs_key_synthesizes_and_transcribes():
    voices = _elevenlabs("GET", "/voices").json()["voices"]
    assert voices
    voice_id = voices[0]["voice_id"]
    assert isinstance(voice_id, str) and voice_id

    models = _elevenlabs("GET", "/models").json()
    tts_models = [
        model["model_id"]
        for model in models
        if model.get("can_do_text_to_speech") is True
    ]
    assert tts_models
    if "eleven_flash_v2_5" in tts_models:
        model_id = "eleven_flash_v2_5"
    else:
        model_id = tts_models[0]

    audio = _elevenlabs(
        "POST",
        f"/text-to-speech/{voice_id}",
        headers={"Accept": "audio/mpeg"},
        json={"text": _SPOKEN, "model_id": model_id},
    )
    assert audio.headers["content-type"].startswith("audio/")
    assert audio.content

    transcript = _elevenlabs(
        "POST",
        "/speech-to-text",
        data={"model_id": "scribe_v2"},
        files={"file": ("hello.mp3", audio.content, "audio/mpeg")},
    )
    text = transcript.json()["text"]
    assert isinstance(text, str) and "hello" in text.casefold()
