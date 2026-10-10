from fastapi import APIRouter, Request
from starlette.datastructures import UploadFile
from starlette.concurrency import run_in_threadpool

from app.api.errors import error_response, finish

router = APIRouter()


@router.post("/requests")
async def create_request(request: Request):
    form = await request.form()
    patient_id = form.get("patient_id")
    text = form.get("text")
    audio = form.get("audio")
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
    return await run_in_threadpool(_process_request, patient_id, text, audio_bytes)


def _process_request(patient_id: str, text: str | None, audio_bytes: bytes | None):
    import app.api.db as api_db
    import app.agents.doctor as doctor

    with api_db.get_session() as session:
        if audio_bytes is None:
            result = doctor.route_doctor_request(
                patient_id,
                text,
                "typed",
                session=session,
            )
            return finish(result)

        from app.speech.hook import SpeechHook

        transcript = SpeechHook().transcribe(audio_bytes)
        result = doctor.route_doctor_request(
            patient_id,
            transcript,
            "voice",
            session=session,
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
