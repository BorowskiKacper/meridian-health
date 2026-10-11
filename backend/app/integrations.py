"""Provider calls shared by the live adapters, with safe client-facing errors."""

import json
import math

from google import genai
from google.genai import types
from pydantic import BaseModel

from app import config
from app.privacy.names import restore_prompt, scrub_data, scrub_prompt


class IntegrationError(RuntimeError):
    def __init__(self, service, message):
        self.service = service
        super().__init__(message)


def gemini_json(instruction, payload, schema: type[BaseModel], *, parts=None):
    if not config.GEMINI_API_KEY:
        raise IntegrationError("Gemini", "Gemini is not configured on the server.")
    data, alias = scrub_data(payload)
    content = json.dumps(data, default=str)
    content, alias = scrub_prompt(content, alias)
    outgoing = []
    for part in parts or []:
        if isinstance(part, str):
            part, alias = scrub_prompt(part, alias)
        outgoing.append(part)
    try:
        with genai.Client(api_key=config.GEMINI_API_KEY, http_options={"timeout": 90000, "retry_options": {"attempts": 1}}) as client:
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=[*outgoing, content],
                config=types.GenerateContentConfig(
                    system_instruction=instruction,
                    response_mime_type="application/json",
                    response_json_schema=schema.model_json_schema(),
                    temperature=0,
                ),
            )
            raw = restore_prompt(response.text or "", alias)
            return schema.model_validate_json(raw)
    except Exception:
        raise IntegrationError("Gemini", "Gemini could not complete this request. Try again; no chart changes were committed.") from None


def embed_text(text):
    if not config.GEMINI_API_KEY:
        raise IntegrationError("Gemini", "Gemini embeddings are not configured on the server.")
    if isinstance(text, str):
        text, _alias = scrub_prompt(text)
    try:
        with genai.Client(api_key=config.GEMINI_API_KEY, http_options={"timeout": 30000, "retry_options": {"attempts": 1}}) as client:
            response = client.models.embed_content(
                model=config.EMBEDDING_MODEL, contents=text,
                config={"output_dimensionality": config.EMBEDDING_DIMENSION},
            )
        values = response.embeddings[0].values
        if len(values) != config.EMBEDDING_DIMENSION or not all(math.isfinite(v) for v in values):
            raise ValueError("Invalid embedding")
        return values
    except Exception:
        raise IntegrationError("Gemini", "The note embedding could not be generated. No changes were committed.") from None
