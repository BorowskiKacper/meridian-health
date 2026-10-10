"""Gemini calls for doctor routing. Tests replace complete."""

import json

from google.genai import types

from app import config

_ANSWER = {
    "type": "OBJECT",
    "properties": {
        "text": {"type": "STRING"},
        "citations": {"type": "ARRAY"},
    },
    "required": ["text", "citations"],
}

_RESEARCH_TOOLS = ["search_guidelines", "search_medical_web", "search_patient_notes"]
_REMINDER_TOOLS = ["search_guidelines", "search_medical_web"]

_SCHEMAS = {
    "classify": {
        "type": "OBJECT",
        "properties": {
            "route": {
                "type": "STRING",
                "enum": ["chart_update", "clinical_question", "check_screenings"],
            }
        },
        "required": ["route"],
    },
    "chart": {
        "type": "OBJECT",
        "properties": {"suggestions": {"type": "ARRAY"}},
        "required": ["suggestions"],
    },
    "research": {
        "type": "OBJECT",
        "properties": {
            "answer": _ANSWER,
            "recommends_action": {"type": "BOOLEAN"},
            "tool_calls": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "name": {"type": "STRING", "enum": _RESEARCH_TOOLS},
                        "text": {"type": "STRING"},
                        "corpus": {"type": "STRING", "enum": ["uspstf", "pubmed"]},
                        "query": {"type": "STRING"},
                    },
                },
            },
        },
        "required": ["answer", "recommends_action", "tool_calls"],
    },
    "reminders": {
        "type": "OBJECT",
        "properties": {
            "suggestions": {"type": "ARRAY"},
            "answer": {"type": "STRING"},
            "up_to_date": {"type": "BOOLEAN"},
            "tool_calls": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "name": {"type": "STRING", "enum": _REMINDER_TOOLS},
                        "text": {"type": "STRING"},
                        "corpus": {"type": "STRING", "enum": ["uspstf", "pubmed"]},
                    },
                },
            },
        },
        "required": ["suggestions", "answer", "up_to_date", "tool_calls"],
    },
    "verify": {
        "type": "OBJECT",
        "properties": {
            "supported": {"type": "ARRAY"},
            "removed": {"type": "ARRAY"},
        },
        "required": ["supported", "removed"],
    },
}


def complete(task, payload):
    if task not in _SCHEMAS:
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
            response_schema=_SCHEMAS[task],
        ),
    )
    return json.loads(response.text or "")
