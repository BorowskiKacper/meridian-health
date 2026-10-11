"""Exact scripted sentences never fall through to a model call."""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
from uuid import uuid4

DIRECTORY = Path(__file__).parent
PROMPTS = json.loads((DIRECTORY / "prompts.json").read_text(encoding="utf-8"))


def find_prompt(patient_id, text):
    return next((p for p in PROMPTS if p["patient_id"] == (str(patient_id) if patient_id else None) and p["text"] == text), None)


@lru_cache(maxsize=1)
def load_answers():
    return json.loads((DIRECTORY / "answers.json").read_text(encoding="utf-8"))


def cached_response(patient_id, text, *, session=None):
    prompt = find_prompt(patient_id, text)
    if prompt is None:
        return None
    entry = load_answers().get(prompt["id"])
    if not entry or entry.get("prompt") != prompt:
        return {"error": {"code": "invalid_state", "message": "This demo answer has not been captured. Rebuild the demo cache before using this prompt."}}
    response = deepcopy(entry["response"])
    response["request_id"] = str(uuid4())
    response["transcript"] = text
    # Captured proposal IDs belonged to the rolled-back build transaction.
    # Create normal pending proposals, preserving the existing approval flow.
    if patient_id and session is not None:
        from datetime import datetime, timezone
        from app.db.repositories import insert_request
        from app.mcp.tools import propose_change
        insert_request(session, {"id": response["request_id"], "patient_id": patient_id,
                       "channel": "typed", "role": "doctor", "transcript": text,
                       "route": prompt["route"], "created_at": datetime.now(timezone.utc)})
        proposals = []
        for proposal in response["suggestions"]:
            proposal["request_id"] = response["request_id"]
            stored = propose_change(patient_id, proposal, session=session)
            if "error" in stored:
                return stored
            proposals.append(stored)
        response["suggestions"] = proposals
    return response
