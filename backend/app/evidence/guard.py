"""Reject identifiers before any evidence search leaves the process."""

import re

# Full calendar dates, ids, and phone numbers. Ages, bare years, and durations stay.
_FORBIDDEN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r"|NW-\d+"
    r"|\+\d{10,15}"
    r"|(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)"
    r"|(?<!\d)\d{1,2}/\d{1,2}/\d{4}(?!\d)"
    r"|(?i:\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\b\.?\s+\d{1,2}(?:st|nd|rd|th)?,\s*\d{4}\b)"
)


def reject_identifiers(text):
    """Raise ValueError when text contains an id, phone number, or full date."""
    if _FORBIDDEN.search(text):
        raise ValueError(
            "text contains a patient id, member id, phone number, or full date"
        )
