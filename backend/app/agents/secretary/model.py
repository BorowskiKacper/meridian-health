"""Gemini calls for secretary chat. Tests replace complete."""

import json

from google.genai import types

from app import config

_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "tool_calls": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {
                        "type": "STRING",
                        "enum": ["get_coverage", "search_payer_docs", "web_search"],
                    },
                    "text": {"type": "STRING"},
                },
            },
        },
        "answer": {
            "type": "OBJECT",
            "properties": {
                "text": {"type": "STRING"},
                "citations": {"type": "ARRAY"},
            },
            "required": ["text", "citations"],
        },
    },
    "required": ["tool_calls", "answer"],
}


def complete(task, payload):
    if task != "secretary":
        raise ValueError(task)
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    from google import genai

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=json.dumps({"task": task, "payload": payload}),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_SCHEMA,
        ),
    )
    return json.loads(response.text or "")
