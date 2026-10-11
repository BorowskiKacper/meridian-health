"""Replace one patient's name in prompt text sent to Gemini or Snowflake.

Callers bind the chart display name. Outbound prompt strings are scanned with
a regex for that name and rewritten with one random first and last name.
Gemini replies are mapped back so the chart still shows the recorded name.
"""

import re
import secrets
from contextlib import contextmanager
from contextvars import ContextVar, copy_context

_PATIENT_NAME = ContextVar("llm_patient_name", default=None)

# Uncommon given names, disjoint from the surnames below, so a reply can be
# mapped back to the chart name without colliding with JSON keys.
_FIRST_NAMES = (
    "Avery",
    "Blake",
    "Cameron",
    "Dakota",
    "Elliot",
    "Finley",
    "Harper",
    "Kendall",
    "Marlow",
    "Quinn",
    "Reese",
    "Rowan",
    "Sawyer",
    "Shiloh",
    "Sutton",
    "Tatum",
)
_LAST_NAMES = (
    "Adler",
    "Beckett",
    "Callahan",
    "Dalton",
    "Ellison",
    "Farrell",
    "Hollister",
    "Iverson",
    "Keating",
    "Langford",
    "Mercer",
    "Pembroke",
    "Prescott",
    "Ramsey",
    "Whitaker",
    "Yardley",
)


class _Alias:
    def __init__(self, tokens, first, last):
        self.tokens = tokens
        self.first = first
        self.last = last
        self.forward = _name_pattern(tokens)
        self.backward = _alias_pattern(first, last)


def _tokens(name):
    return [part for part in re.split(r"\s+", name.strip()) if part]


def _letters(token):
    return re.sub(r"[^\w]", "", token, flags=re.UNICODE)


def _name_pattern(tokens):
    if not tokens:
        return None
    first, last = tokens[0], tokens[-1]
    parts = []
    if len(tokens) >= 2 and _letters(first) and _letters(last):
        parts.append(re.escape(last) + r"\s*,\s*" + re.escape(first))
        parts.append(r"\s+".join(re.escape(token) for token in tokens))
    seen = set()
    for token in sorted(set(tokens), key=len, reverse=True):
        key = token.casefold()
        if key in seen or len(_letters(token)) < 2:
            continue
        seen.add(key)
        parts.append(re.escape(token))
    if not parts:
        return None
    return re.compile(
        r"(?<!\w)(?:" + "|".join(parts) + r")(?!\w)",
        re.IGNORECASE,
    )


def _alias_pattern(first, last):
    parts = [
        re.escape(last) + r"\s*,\s*" + re.escape(first),
        re.escape(first) + r"\s+" + re.escape(last),
        re.escape(first),
        re.escape(last),
    ]
    return re.compile(
        r"(?<!\w)(?:" + "|".join(parts) + r")(?!\w)",
        re.IGNORECASE,
    )


def _token_in(text, token):
    return (
        re.search(
            r"(?<!\w)" + re.escape(token) + r"(?!\w)",
            text,
            re.IGNORECASE,
        )
        is not None
    )


def _choose_alias(tokens, text):
    blocked = {token.casefold() for token in tokens}
    for _ in range(32):
        first = secrets.choice(_FIRST_NAMES)
        last = secrets.choice(_LAST_NAMES)
        if first.casefold() in blocked or last.casefold() in blocked:
            continue
        if first.casefold() == last.casefold():
            continue
        if _token_in(text, first) or _token_in(text, last):
            continue
        return first, last
    alphabet = "abcdefghijklmnop"
    for _ in range(20):
        first = "Ren" + "".join(secrets.choice(alphabet) for _ in range(4))
        last = "Sol" + "".join(secrets.choice(alphabet) for _ in range(4))
        first = first.capitalize()
        last = last.capitalize()
        if first.casefold() in blocked or last.casefold() in blocked:
            continue
        if _token_in(text, first) or _token_in(text, last):
            continue
        return first, last
    nonce = secrets.token_hex(3)
    return f"Ren{nonce}", f"Sol{nonce}"


def _is_json_key(text, start, end):
    """Leave object keys alone. A patient named Active must not rewrite "active"."""
    if start < 1 or text[start - 1] != '"':
        return False
    return re.match(r'"\s*:', text[end:]) is not None


def _forward_replacement(match, alias):
    text = match.group(0)
    first = alias.tokens[0]
    last = alias.tokens[-1]
    if "," in text:
        return f"{alias.last}, {alias.first}"
    if re.search(r"\s", text):
        return f"{alias.first} {alias.last}"
    if first.casefold() != last.casefold() and text.casefold() == last.casefold():
        return alias.last
    return alias.first


def _backward_replacement(match, alias):
    text = match.group(0)
    first = alias.tokens[0]
    last = alias.tokens[-1]
    if "," in text:
        return f"{last}, {first}"
    if re.search(r"\s", text):
        return " ".join(alias.tokens)
    if text.casefold() == alias.last.casefold() and first.casefold() != last.casefold():
        return last
    return first


def _sub(pattern, text, repl):
    if pattern is None or not isinstance(text, str):
        return text

    def guarded(match):
        if _is_json_key(text, match.start(), match.end()):
            return match.group(0)
        return repl(match)

    return pattern.sub(guarded, text)


def _alias_for(texts):
    name = _PATIENT_NAME.get()
    if not isinstance(name, str) or not name.strip():
        return None
    tokens = _tokens(name)
    pattern = _name_pattern(tokens)
    blobs = [text for text in texts if isinstance(text, str)]
    if pattern is None or not any(pattern.search(text) for text in blobs):
        return None
    first, last = _choose_alias(tokens, "\n".join(blobs))
    return _Alias(tokens, first, last)


def scrub_prompts(texts, alias=None):
    """Replace the bound patient name in each string. Non-strings pass through."""
    if alias is None:
        alias = _alias_for(texts)
    if alias is None:
        return list(texts), None
    scrubbed = [
        _sub(alias.forward, text, lambda match: _forward_replacement(match, alias))
        if isinstance(text, str)
        else text
        for text in texts
    ]
    return scrubbed, alias


def scrub_prompt(text, alias=None):
    """Scan one outbound prompt and replace the bound patient's name."""
    scrubbed, alias = scrub_prompts([text], alias)
    return scrubbed[0], alias


def restore_prompt(text, alias):
    """Map a Gemini reply back to the chart name. Pass through when no alias was used."""
    if alias is None or not isinstance(text, str):
        return text
    return _sub(alias.backward, text, lambda match: _backward_replacement(match, alias))


def _walk_strings(value, found):
    if isinstance(value, str):
        found.append(value)
        return
    if isinstance(value, dict):
        for item in value.values():
            _walk_strings(item, found)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _walk_strings(item, found)


def _replace_strings(value, alias):
    if isinstance(value, str):
        return _sub(alias.forward, value, lambda match: _forward_replacement(match, alias))
    if isinstance(value, dict):
        return {key: _replace_strings(item, alias) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_strings(item, alias) for item in value]
    if isinstance(value, tuple):
        return tuple(_replace_strings(item, alias) for item in value)
    return value


def scrub_data(value, alias=None):
    """Replace the bound patient name inside nested string values."""
    if alias is None:
        found = []
        _walk_strings(value, found)
        alias = _alias_for(found)
    if alias is None:
        return value, None
    return _replace_strings(value, alias), alias


@contextmanager
def bind_patient_name(display_name):
    """Bind the chart name scanned for in prompts sent on this context."""
    if not isinstance(display_name, str) or not display_name.strip():
        yield
        return
    token = _PATIENT_NAME.set(display_name.strip())
    try:
        yield
    finally:
        _PATIENT_NAME.reset(token)


def display_name_for(session, patient_id):
    """Chart name for a patient id, or None when the row cannot be read."""
    if session is None or patient_id is None:
        return None
    try:
        from app.db.repositories import get_patient

        patient = get_patient(session, patient_id)
    except (TypeError, ValueError):
        return None
    if not isinstance(patient, dict):
        return None
    name = patient.get("display_name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return None


def submit_in_context(pool, fn, *args, **kwargs):
    """Run fn in a worker with this thread's patient-name binding copied over.

    Thread pools do not inherit context vars. Evidence search and verification
    run there, and those calls still have to see the bound chart name.
    """
    ctx = copy_context()
    return pool.submit(ctx.run, fn, *args, **kwargs)
