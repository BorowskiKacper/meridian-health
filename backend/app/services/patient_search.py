"""Bounded patient-directory lookup; no clinical chart is loaded for results."""
from sqlalchemy import String, and_, cast, func, or_, select

from app.db.models import Patient


def search_patients(query, limit, *, session):
    query = query.strip()
    statement = select(Patient)
    if query:
        tokens = query.casefold().split()
        name_match = and_(*(func.lower(Patient.display_name).contains(token, autoescape=True) for token in tokens))
        record_query = query.casefold().removeprefix("r-").replace("-", "")
        id_match = func.replace(cast(Patient.id, String), "-", "").contains(record_query, autoescape=True) if record_query else False
        dob_match = cast(Patient.date_of_birth, String).contains(query, autoescape=True)
        statement = statement.where(or_(name_match, id_match, dob_match))
    rows = session.scalars(statement.order_by(Patient.display_name, Patient.id).limit(limit + 1)).all()
    return {
        "patients": [{"id": str(row.id), "display_name": row.display_name,
                      "date_of_birth": row.date_of_birth.isoformat(), "sex": row.sex}
                     for row in rows[:limit]],
        "has_more": len(rows) > limit,
    }
