from fastapi import APIRouter, Request
from starlette.datastructures import UploadFile
from starlette.concurrency import run_in_threadpool

from app.api.errors import error_response, finish

router = APIRouter()


@router.post("/chat")
async def general_chat(request: Request):
    form = await request.form()
    if form.get("patient_id") is not None or form.get("route") not in (None, "clinical_question"):
        return error_response("validation_error", "General chat has no patient chart. Open a patient conversation for chart changes or screening review.")
    text, audio = form.get("text"), form.get("audio")
    if isinstance(text, str) == isinstance(audio, UploadFile):
        return error_response("validation_error", "Send exactly one of text or audio.")
    audio_bytes = await audio.read() if isinstance(audio, UploadFile) else None
    return await run_in_threadpool(_general_chat, text, audio_bytes)


def _general_chat(text, audio):
    from uuid import uuid4
    from app.agents.doctor import _research_answer
    if audio is not None:
        from app.speech.hook import SpeechHook
        text = SpeechHook().transcribe(audio)
    if not isinstance(text, str) or not text.strip():
        return error_response("validation_error", "A nonempty question or recognized transcript is required.")
    answer = _research_answer(None, text, None)
    spoken = None
    if audio is not None and answer.get("text"):
        spoken = SpeechHook().synthesize(answer["text"])
    return {"request_id": str(uuid4()), "transcript": text, "route": "clinical_question", "suggestions": [], "answer": answer, "spoken_text": answer["text"] if audio is not None else None, "audio_base64": spoken}


@router.post("/requests/preview")
async def preview_request(request: Request):
    form = await request.form()
    patient_id, text, audio = form.get("patient_id"), form.get("text"), form.get("audio")
    if not isinstance(patient_id, str) or not patient_id.strip():
        return error_response("validation_error", "patient_id is required.")
    if isinstance(text, str) == isinstance(audio, UploadFile):
        return error_response("validation_error", "Send exactly one of text or audio.")
    audio_bytes = await audio.read() if isinstance(audio, UploadFile) else None
    return await run_in_threadpool(_preview_request, patient_id, text, audio_bytes)


def _preview_request(patient_id, text, audio):
    import app.api.db as api_db
    from app.mcp.tools import preview_request_route
    if audio is not None:
        from app.speech.hook import SpeechHook
        text = SpeechHook().transcribe(audio)
    with api_db.get_session() as session:
        return finish(preview_request_route(patient_id, text, session=session))


@router.post("/requests")
async def create_request(request: Request):
    form = await request.form()
    patient_id = form.get("patient_id")
    text = form.get("text")
    audio = form.get("audio")
    route = form.get("route")
    reviewed_transcript = form.get("reviewed_transcript")
    if reviewed_transcript is not None and (not isinstance(audio, UploadFile) or not isinstance(reviewed_transcript, str) or not reviewed_transcript.strip()):
        return error_response("validation_error", "A reviewed transcript requires audio and nonempty text.")
    if route is not None and route not in {"chart_update", "clinical_question", "check_screenings"}:
        return error_response("validation_error", "Unknown request route.")
    text_present = isinstance(text, str)
    audio_present = isinstance(audio, UploadFile)
    if not isinstance(patient_id, str) or not patient_id.strip():
        return error_response("validation_error", "patient_id is required.")
    if text_present == audio_present:
        return error_response(
            "validation_error",
            "Send exactly one of text or audio.",
        )

    audio_bytes = await audio.read() if audio_present else None
    return await run_in_threadpool(_process_request, patient_id, text if text_present else None, audio_bytes, route, reviewed_transcript)


def _process_request(patient_id: str, text: str | None, audio_bytes: bytes | None, route: str | None = None, reviewed_transcript: str | None = None):
    import app.api.db as api_db
    import app.agents.doctor as doctor

    routing = {"route": route} if route is not None else {}
    if audio_bytes is None:
        with api_db.get_session() as session:
            result = doctor.route_doctor_request(
                patient_id, text, "typed", session=session, **routing,
            )
            return finish(result)

    from app.speech.hook import SpeechHook

    # Preserve the confirmed transcript and reject unrecognized speech before routing.
    transcript = reviewed_transcript if reviewed_transcript is not None else SpeechHook().transcribe(audio_bytes)
    if not isinstance(transcript, str) or not transcript.strip():
        return error_response("validation_error", "Audio could not be transcribed.")
    with api_db.get_session() as session:
        result = doctor.route_doctor_request(
            patient_id, transcript, "voice", session=session, **routing,
        )
        if (
            isinstance(result, dict)
            and set(result) != {"error"}
            and result.get("spoken_text") is not None
        ):
            copied = dict(result)
            copied["audio_base64"] = SpeechHook().synthesize(result["spoken_text"])
            return copied
        return finish(result)
