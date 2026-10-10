"""Gemini Google Search grounding. Returns redirect URIs, not final pages."""

from google import genai
from google.genai import types

from app import config


def _answer_text(response):
    try:
        text = response.text
    except (AttributeError, ValueError):
        return ""
    return text or ""


def _metadata(response):
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return None
    return getattr(candidates[0], "grounding_metadata", None)


def grounded_search(text):
    """Run one grounded Gemini call.

    Returns text, grounding_chunks ({uri, title}), and grounding_supports
    ({segment_text, chunk_indices}). Chunk URIs are Google redirect links.
    """
    client = genai.Client(api_key=config.GEMINI_API_KEY, http_options={"timeout": 90000, "retry_options": {"attempts": 1}})
    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=text,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        ),
    )
    chunks = []
    supports = []
    metadata = _metadata(response)
    if metadata is not None:
        for chunk in metadata.grounding_chunks or []:
            web = getattr(chunk, "web", None)
            uri = getattr(web, "uri", None) if web is not None else None
            title = getattr(web, "title", None) if web is not None else None
            chunks.append({"uri": uri or "", "title": title or ""})
        for support in metadata.grounding_supports or []:
            segment = getattr(support, "segment", None)
            segment_text = getattr(segment, "text", None) if segment is not None else None
            indices = list(getattr(support, "grounding_chunk_indices", None) or [])
            supports.append(
                {"segment_text": segment_text or "", "chunk_indices": indices}
            )
    return {
        "text": _answer_text(response),
        "grounding_chunks": chunks,
        "grounding_supports": supports,
    }
