"""Predefined, read-only phone demo commands; chart values always remain live."""

PROMPT = "Open John's vitals"


def cached_navigation(text):
    normalized = text.strip().replace('\u2019', "'").casefold().rstrip('.!?').strip()
    if normalized not in {"open john's vitals", "open john roe's vitals", 'open johns vitals'}:
        return None
    # Resolve the named demo patient normally; never reuse another chart's context.
    return {'patient_query': 'John Roe', 'needs_patient': True, 'route': None, 'views': ['vitals']}
