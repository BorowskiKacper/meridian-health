# Remaining backend

Build contract for the backend work that `builder-contracts.md` requires and the code does not do yet. ElevenLabs is specified here in full. The other sections are the remaining vendor adapters and the Snowflake load.

This file does not replace `builder-contracts.md`. It does not add a JSON field, a route, a table, or a dependency.

## What wins

| File | Wins on |
|---|---|
| `builder-contracts.md` | names, payloads, tables, owners, invariants |
| `system-design-routing-2.md` | behavior `builder-contracts.md` does not specify |
| `backend-remaining.md` (this file) | how the unfinished backend pieces call their vendors |
| `system-design-graph.md` | nothing. It is a superseded draft. The table below is the only use of it |

If this file and `builder-contracts.md` disagree, `builder-contracts.md` wins. `system-design-routing-2.md` still fills behavior the contract does not specify, including a spoken summary on every voice route.

## Already built

Do not rebuild these. They are in the tree and match the contract:

- Every route in `builder-contracts.md`, including `POST /requests` with `text` or `audio`.
- Repositories, seed, MCP tools, evidence functions, approval, reminders, WhatsApp send, eligibility, appointments, secretary chat, and the doctor agent loop.
- Snowflake Cortex Search queries in `backend/app/evidence/cortex.py` (`httpx`, bearer `SNOWFLAKE_PAT`).
- Google Search grounding and the medical allowlist in `backend/app/evidence/`.
- The eligibility summary call to `gemini-3.6-flash`.
- Lab photo upload to the private S3 bucket named by `S3_BUCKET`. `documents.storage_key` is the object key. The upload runs after the document and suggestion rows are written.
- `SpeechHook` is called only from `backend/app/api/routes/requests.py`.

## What the graph asked for that this build does not do

| Graph idea | Decision |
|---|---|
| `POST /dictations` and `POST /asks`, Dictate/Ask toggle | Drop. One doctor route, `POST /requests`. |
| ElevenLabs on those two routes, and a separate phone TTS summary for Ask | Drop as routes. Voice still uses the one speech hook below. |
| AWS HealthScribe instead of ElevenLabs | Drop. This build calls ElevenLabs. |
| Stedi or any live payer | Drop. Coverage stays seeded mock data. |
| Nightly reminder agent, APScheduler, scheduled WhatsApp sends | Drop. `POST /demo/run-reminders` is the only sender. |
| Snowflake MCP, a Snowflake connector package | Drop. Cortex Search stays REST through `httpx`. |
| Vector search over notes | Drop. Embeddings are stored. `search_patient_notes` stays Postgres full-text. |
| Streaming research answers or streaming audio | Drop. One JSON body. `audio_base64` is optional. |
| Store request audio in S3 | Drop. S3 holds lab photos only. |
| Production BAA, Vertex AI, AgentCore, HealthLake, Cognito | Drop. Out of this backend. |
| UI, OpenAPI client, 3D body mesh | Drop. Not backend. |

Google's display rules for grounded search are a UI concern. Do not add a suggestions field to any JSON body.

## Locked choices

- No new package. ElevenLabs uses `httpx`, the same way Snowflake does. Gemini keeps `google-genai`.
- Secrets stay the names already in `backend/app/config.py`. New model and voice ids are constants there, next to `GEMINI_MODEL`.
- Tests fake every vendor. A missing key must not open a socket.
- Agents still accept text. Only `POST /requests` calls `SpeechHook`.
- `spoken_text` and `audio_base64` stay null on a typed request. The doctor agent still sets `audio_base64` to null. The route is the only writer of a non-null `audio_base64`.

## ElevenLabs

Owner: the API worker. Code stays in `backend/app/speech/hook.py` plus the voice branch of `backend/app/api/routes/requests.py`. The doctor agent owns the words in `spoken_text`. It does not call ElevenLabs.

Constants in `backend/app/config.py`:

| Constant | Value |
|---|---|
| `ELEVENLABS_STT_MODEL` | `scribe_v2_medical` |
| `ELEVENLABS_TTS_MODEL` | `eleven_multilingual_v2` |
| `ELEVENLABS_VOICE_ID` | `JBFqnCBsd6RMkjVDRZzb` |
| `ELEVENLABS_TTS_FORMAT` | `mp3_44100_128` |

`ELEVENLABS_API_KEY` is the existing env var. Header on both calls is `xi-api-key`. No webhook, diarization, entity redaction, or logging flag. Language is `eng`. Timeouts are 60 seconds for transcription and 30 seconds for synthesis.

### Speech to text

`SpeechHook.transcribe(audio)` sends the raw upload bytes.

`POST https://api.elevenlabs.io/v1/speech-to-text`

Multipart fields: `file` (the bytes, filename `audio`) and `model_id` (`ELEVENLABS_STT_MODEL`). Also send `language_code=eng`. Do not set `webhook`, `diarize`, or `use_multi_channel`.

The transcript is the response JSON field `text`, stripped. Return that string.

Return `None` when the key is empty, the body is empty, the status is not 2xx, the call times out, or `text` is missing or blank. Do not raise. Do not fall back to another vendor or to `scribe_v2`.

`POST /requests` calls `route_doctor_request` only when the transcript is a non-empty string. Otherwise it returns `400` `validation_error` with message `Audio could not be transcribed.` and does not write a `requests` row.

### Spoken text

Set only when `channel` is `voice`. Citations are not spoken.

| Route | `spoken_text` |
|---|---|
| `chart_update` | The string already built from suggestion reasons. |
| `clinical_question` | `answer.text`. |
| `check_screenings` with new suggestions | The same shape as a chart read-back, using each suggestion `reason`. |
| `check_screenings` with an up-to-date answer | `answer.text`. |

`audio_base64` on the agent result stays null.

### Speech synthesis

When the voice result has a non-empty `spoken_text`, the route sets `audio_base64` from `SpeechHook.synthesize(spoken_text)`.

`POST https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}?output_format=mp3_44100_128`

JSON body: `{ "text": "<spoken_text>", "model_id": "eleven_multilingual_v2" }`.

Return standard base64 of the response bytes, ASCII, with no `data:` prefix. Return `None` when the key is empty, the status is not 2xx, the call times out, or the body is empty. The route then returns the JSON with `audio_base64` null and status 200.

Typed requests never call `synthesize`.

### Speech tests

Keep the current test: an empty key returns `None` from both methods and does not open a socket.

Add tests that set `ELEVENLABS_API_KEY` and fake `httpx`. They check the two URLs, the `xi-api-key` header, `model_id`, and that synthesis returns base64 of the fake bytes. A non-2xx response returns `None`.

Add a route test: audio whose transcription is `None` returns `400` `validation_error` and does not call `route_doctor_request`. The existing test that fakes a transcript still expects `200`, `spoken_text`, and `audio_base64` from the fake hook.

## Gemini agent adapters

The doctor and secretary loops are done. The model functions they call are not.

`backend/app/agents/doctor/model.py` `complete(task, payload)` raises `NotImplementedError`. `backend/app/agents/secretary/model.py` does not exist. Secretary chat imports it.

Owner: Doctor agents for `backend/app/agents/doctor/model.py`. Secretary for `backend/app/agents/secretary/model.py`. Neither file imports Snowflake, ElevenLabs, or a repository.

Both call `gemini-3.6-flash` through `google-genai` with `response_mime_type` `application/json` and a response schema, the same way `ask_model` does in `backend/app/services/eligibility.py`. One call per `complete`. An empty `GEMINI_API_KEY` raises. Tests keep replacing `complete`.

Do not change the payload the agent already passes in. Do not add a tool the contract does not list. Return only the fields below. The existing loop executes `tool_calls`, strips identifiers, and runs `verify_claims`.

### `complete("classify", {"text"})`

```json
{ "route": "chart_update" }
```

`route` is `chart_update`, `clinical_question`, or `check_screenings`.

### `complete("chart", {"text", "context"})`

```json
{ "suggestions": [] }
```

Each suggestion is the contract suggestion without `id` and without `unconfirmed`. `status` is `pending`. `source` is `chart_agent`. `target_table` and `after` stay on the allowlist. The loop stores them through `propose_change`.

### `complete("research", payload)`

```json
{
  "answer": { "text": "", "citations": [] },
  "recommends_action": false,
  "tool_calls": []
}
```

`tool_calls` may include `search_guidelines` (`text`, `corpus` of `uspstf` or `pubmed`), `search_medical_web` (`text`), and `search_patient_notes` (`query`). No `web_search`. No `propose_change`. A recommendation still needs a `baseline` or `guideline` citation after `verify_claims`. The loop already replaces the answer when that citation is missing.

### `complete("reminders", payload)`

```json
{
  "suggestions": [],
  "answer": "Screenings are up to date.",
  "up_to_date": true,
  "tool_calls": []
}
```

`tool_calls` may include `search_guidelines` and `search_medical_web` only. A proposed row is a `reminder_change` with a `baseline` citation. `up_to_date` true means no suggestions. The loop already drops a change that loses its `baseline` citation in `verify_claims`.

### `complete("verify", {"text", "citations"})`

```json
{
  "supported": [{ "sentence": "Screen adults aged 45 to 49 years.", "citation_indexes": [0] }],
  "removed": []
}
```

`citation_indexes` are integers into the citations array. `verify_claims` already drops a sentence that is not supported and drops unused citations. The prompt checks each sentence against the cited `passage` only.

### `complete("secretary", {"text"})`

```json
{
  "tool_calls": [],
  "answer": { "text": "", "citations": [] }
}
```

`tool_calls` may include `get_coverage`, `search_payer_docs` (`text`), and `web_search` (`text`). The loop ignores `propose_change`. The answer may cite `payer` and `web`.

### Agent-adapter tests

Existing agent tests keep faking `complete`. Add one test module per adapter that fakes the Gemini client and checks the schema for each task. Those tests do not hit the network.

## Note embeddings

Owner: Approval. `embed_text` in `backend/app/services/approval.py` returns 768 zeros. Replace that body.

Call `gemini-embedding-001` with `output_dimensionality` 768, the constants `EMBEDDING_MODEL` and `EMBEDDING_DIMENSION`. Return a list of 768 floats.

If the key is empty, the call fails, or the vector length is not 768, return `None`. Do not store zeros. `approve_suggestions` still commits the chart write and stores `notes.embedding` as null. Seed still writes no embedding.

`search_patient_notes` stays full-text. Do not add a vector query.

The approval tests that replace `embed_text` stay. Add one test that fakes the embedding client, expects 768 floats, and expects `None` when the fake client fails.

## Lab photo vision

Owner: Labs. `extract_analytes` in `backend/app/services/labs.py` returns `[]`. S3 upload stays as it is.

`extract_analytes(content, media_type)` sends the bytes to `gemini-3.6-flash` as an image of `media_type` and asks for JSON:

```json
[
  {
    "name": "LDL",
    "value": 162,
    "unit": "mg/dL",
    "observed_at": "2026-09-01T00:00:00Z",
    "confidence": 0.9,
    "flag": "out_of_range"
  }
]
```

`flag` is `ok`, `low_confidence`, or `out_of_range`. `confidence` is a number from 0 to 1. Drop an item missing `name`, `value`, `unit`, or `observed_at`. An empty key or a failed call returns `[]`. The document row and the S3 object are still saved. No `observations` row is written.

The lab tests that replace `extract_analytes` stay. Add one test that fakes the vision client and checks that `low_confidence` and `out_of_range` are copied onto `validation_flags`.

## Snowflake corpora

Owner: Evidence. Query code is done. The three Cortex Search services are not loaded.

Services, already named in `backend/app/config.py`:

| Constant | File | Tier the query assigns |
|---|---|---|
| `USPSTF_SEARCH` | `backend/ingest/corpus/uspstf.jsonl` | `baseline` |
| `PUBMED_SEARCH` | `backend/ingest/corpus/pubmed.jsonl` | `literature` |
| `PAYER_DOCS_SEARCH` | `backend/ingest/corpus/payer_docs.jsonl` | `payer` |

`pubmed.jsonl` is gitignored. `python backend/ingest/fetch_corpus.py` writes all three. Do not edit `backend/ingest/corpus/` or `backend/ingest/payer_docs/` by hand. Do not change `cortex_search`.

Add `backend/ingest/load_snowflake.py`. It reads those three files and creates or replaces the three services in `SNOWFLAKE_DATABASE`.`SNOWFLAKE_SCHEMA` using the same account, token, and `httpx` client style as `cortex.py`. Each row keeps `source_id`, `title`, `passage`, and `locator`. The script is not imported by the app and is not run in tests.

Done when `cortex_search` against each service can return those four fields for a query that matches a passage in that file. Until someone runs the script, evidence calls still depend on a real Snowflake account and return vendor errors when the services are missing. Tests keep faking `cortex_search`.

## Files this work may change

| Piece | Paths |
|---|---|
| ElevenLabs | `backend/app/speech/hook.py`, `backend/app/api/routes/requests.py`, `backend/app/config.py`, `backend/tests/api/test_speech_hook.py`, `backend/tests/api/test_requests.py` |
| Spoken text for voice research and screenings | `backend/app/agents/doctor/__init__.py`, `backend/tests/agents/doctor/` |
| Doctor model | `backend/app/agents/doctor/model.py`, new tests under `backend/tests/agents/doctor/` |
| Secretary model | `backend/app/agents/secretary/model.py`, new tests under `backend/tests/agents/secretary/` |
| Embeddings | `backend/app/services/approval.py`, `backend/tests/services/test_approval.py` |
| Lab vision | `backend/app/services/labs.py`, `backend/tests/services/test_labs.py` |
| Snowflake load | `backend/ingest/load_snowflake.py` only |

No `web/`, no `mobile/`, no edit to `builder-contracts.md`, and no edit to the corpus files.

## Done when

- A voice `POST /requests` with `ELEVENLABS_API_KEY` set transcribes with Scribe, routes on that text, and returns `audio_base64` for a chart update, a clinical question, and a screening review. Synthesis failure still returns 200 with `audio_base64` null.
- A typed `POST /requests` never calls the hook.
- An empty ElevenLabs key makes no network call. Failed transcription is `400` and writes no request row.
- `complete` for the six tasks returns the JSON in this file from a faked Gemini response.
- Approving a note stores 768 floats, or null if the embedding call fails, and never stores a zero vector.
- A faked vision response becomes pending observation suggestions with the contract flags. The file still goes to S3.
- `load_snowflake.py` is the only new ingest entry point, and tests still fake Snowflake.
