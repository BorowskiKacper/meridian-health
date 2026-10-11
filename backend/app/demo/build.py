"""Run with python -m app.demo.build; existing entries are never recaptured."""
import json
from datetime import datetime, timezone

from fastapi.encoders import jsonable_encoder
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.demo.cache import DIRECTORY, PROMPTS


def main():
    from app.config import DATABASE_URL
    from app.agents.doctor import route_doctor_request, _research_answer

    target = DIRECTORY / "answers.json"
    answers = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
    # Do not use bootstrap/get_engine: this command needs no schema changes.
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        for prompt in PROMPTS:
            if answers.get(prompt["id"], {}).get("prompt") == prompt:
                continue
            print(f"Capturing {prompt['id']}...", flush=True)
            with Session(engine) as session:
                try:
                    session.execute(text('SET LOCAL search_path TO clinic, public'))
                    if prompt["patient_id"]:
                        response = route_doctor_request(prompt["patient_id"], prompt["text"], "typed", session=session, route=prompt["route"], use_demo_cache=False)
                    else:
                        response = {"route": "clinical_question", "transcript": prompt["text"], "answer": _research_answer(None, prompt["text"], None), "suggestions": [], "spoken_text": None, "audio_base64": None}
                    if "error" in response or not (response.get("suggestions") or (response.get("answer") or {}).get("text")):
                        raise RuntimeError(f"No usable live answer for {prompt['id']}")
                    response = jsonable_encoder(response)
                finally:
                    session.rollback()
            response.pop("request_id", None)
            for proposal in response["suggestions"]:
                for field in ("id", "patient_id", "created_at", "status", "unconfirmed"):
                    proposal.pop(field, None)
            answers[prompt["id"]] = {"prompt": prompt, "captured_at": datetime.now(timezone.utc).isoformat(), "response": response}
            temporary = target.with_suffix(".tmp")
            temporary.write_text(json.dumps(answers, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            temporary.replace(target)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
