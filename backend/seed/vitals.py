"""Optional, explicitly synthetic vitals for the three named hackathon patients.

Adds missing records only, never replaces chart observations. Original encounter
dates are retained; these are not measurements taken today.
"""

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from app.db.repositories import get_patient, insert_observation, list_observations_by_patient

DEMO_VITALS = (
    ("33333333-3333-4333-8333-333333333333", "Amy Lee", (
        ("2024-02-06", 64.8, 118, 74, 76),
        ("2024-08-12", 65.1, 116, 72, 72),
        ("2025-08-01", 66.0, 120, 76, 74),
    )),
    ("11111111-1111-4111-8111-111111111111", "Jane Doe", (
        ("2023-03-02", 86.4, None, None, 78),
        ("2023-09-14", 87.1, None, None, 80),
        ("2024-03-01", 88.2, None, None, 76),
        ("2024-09-12", 89.0, None, None, 78),
        ("2025-03-04", 90.1, None, None, 80),
        ("2025-09-09", 91.2, None, None, 82),
    )),
    ("22222222-2222-4222-8222-222222222222", "John Roe", (
        ("2023-06-05", 78.4, None, None, 84),
        ("2024-06-03", 77.8, None, 82, 82),
        ("2025-06-01", 76.9, None, 78, 80),
    )),
)


def seed_vitals(session):
    added = 0
    for patient_id, expected_name, rows in DEMO_VITALS:
        patient = get_patient(session, patient_id)
        if not patient or patient["display_name"] != expected_name:
            continue
        existing = {
            (row["name"], row["unit"], row["observed_at"].date().isoformat())
            for row in list_observations_by_patient(session, patient_id)
        }
        for day, weight, systolic, diastolic, pulse in rows:
            for name, unit, value in (
                ("Body weight", "kg", weight),
                ("Systolic blood pressure", "mmHg", systolic),
                ("Diastolic blood pressure", "mmHg", diastolic),
                ("Heart rate", "beats/min", pulse),
            ):
                key = (name, unit, day)
                if value is None or key in existing:
                    continue
                insert_observation(session, {
                    "id": str(uuid5(NAMESPACE_URL, f"round-demo-vitals/{patient_id}/{name}/{day}")),
                    "patient_id": patient_id,
                    "name": name,
                    "unit": unit,
                    "value": value,
                    "observed_at": datetime.fromisoformat(f"{day}T09:00:00").replace(tzinfo=timezone.utc),
                    "source": "demo_vitals",
                    "document_id": None,
                    "body_region_key": "heart",
                })
                existing.add(key)
                added += 1
    return added
