from datetime import date, datetime, timezone

from app.db.repositories import (
    get_coverage_by_patient,
    get_patient,
    list_allergies_by_patient,
    list_all_specialty_focus,
    list_appointments_by_patient,
    list_body_regions,
    list_conditions_by_patient,
    list_conditions_by_region,
    list_encounters_by_patient,
    list_family_history_by_patient,
    list_medications_by_patient,
    list_medications_by_region,
    list_notes_by_patient,
    list_observations_by_patient,
    list_observations_by_region,
    list_patients,
    list_reminder_rules,
    list_reminders_by_patient,
    list_specialty_focus,
    list_suggestions,
)


def _error(code, message):
    return {"error": {"code": code, "message": message}}


def _zulu(value):
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, date):
        return f"{value.isoformat()}T00:00:00Z"
    return value


def _age(dob):
    if isinstance(dob, datetime):
        dob = dob.date()
    today = datetime.now(timezone.utc).date()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _whole_number(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    number = float(value)
    if number.is_integer():
        return int(number)
    return number


def _patient_summary(patient):
    return {
        "id": patient["id"],
        "display_name": patient["display_name"],
        "age": _age(patient["date_of_birth"]),
    }


def _timeline(session, patient_id):
    events = []
    for condition in list_conditions_by_patient(session, patient_id):
        events.append(
            {
                "at": _zulu(condition["onset_date"]),
                "kind": "condition",
                "label": condition["name"],
            }
        )
    for medication in list_medications_by_patient(session, patient_id):
        events.append(
            {
                "at": _zulu(medication["start_date"]),
                "kind": "medication",
                "label": medication["name"],
            }
        )
    for encounter in list_encounters_by_patient(session, patient_id):
        events.append(
            {
                "at": _zulu(encounter["occurred_at"]),
                "kind": "encounter",
                "label": encounter["summary"],
            }
        )
    events.sort(key=lambda item: item["at"])
    return events


def _trends(session, patient_id):
    grouped = {}
    for observation in list_observations_by_patient(session, patient_id):
        name = observation["name"]
        bucket = grouped.setdefault(
            name,
            {"name": name, "unit": observation["unit"], "points": []},
        )
        bucket["points"].append(
            {
                "at": _zulu(observation["observed_at"]),
                "value": _whole_number(observation["value"]),
            }
        )
    trends = []
    for trend in grouped.values():
        trend["points"].sort(key=lambda point: point["at"])
        trends.append(trend)
    trends.sort(key=lambda trend: trend["name"])
    return trends


def _regions(session, patient_id, specialty):
    focused = {
        row["region_key"] for row in list_specialty_focus(session, specialty)
    }
    conditions_by_region = {}
    for condition in list_conditions_by_patient(session, patient_id):
        conditions_by_region.setdefault(condition["body_region_key"], []).append(
            condition
        )
    regions = []
    for region in list_body_regions(session):
        key = region["region_key"]
        conditions = conditions_by_region.get(key, [])
        emphasis = "focus" if key in focused else "dim"
        pulse = emphasis == "focus" and any(
            row["status"] == "active" for row in conditions
        )
        regions.append(
            {
                "region_key": key,
                "mesh_name": region["mesh_name"],
                "emphasis": emphasis,
                "pulse": bool(pulse),
                "condition_count": len(conditions),
            }
        )
    return regions


def _date_string(value):
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    return None if value is None else str(value)[:10]


def _family(session, patient_id):
    return [
        {
            "relationship": row["relationship"],
            "condition": row["condition"],
            "age_at_diagnosis": row["age_at_diagnosis"],
        }
        for row in list_family_history_by_patient(session, patient_id)
    ]


def _allergies(session, patient_id):
    rows = [
        {
            "id": str(row["id"]),
            "substance": row["substance"],
            "category": row["category"],
            "reaction": row["reaction"],
            "severity": row["severity"],
            "status": row["status"],
            "recorded_on": _date_string(row["recorded_on"]),
        }
        for row in list_allergies_by_patient(session, patient_id)
    ]
    order = {"anaphylaxis": 0, "severe": 1, "moderate": 2, "mild": 3, "none": 4}
    rows.sort(key=lambda row: (order.get(row["severity"], 5), row["substance"]))
    return rows


def _unsubscribe_token(patient_id):
    import app.services.email as email

    return email.unsubscribe_token(patient_id)


def _directory_entry(session, patient):
    return {
        "id": str(patient["id"]),
        "display_name": patient["display_name"],
        "date_of_birth": _date_string(patient["date_of_birth"]),
        "age": _age(patient["date_of_birth"]),
        "sex": patient["sex"],
        "email_opt_in": bool(patient["email_opt_in"]),
        "email": patient["email"],
        "unsubscribe_token": _unsubscribe_token(patient["id"]),
        "family_history": _family(session, patient["id"]),
        "allergies": _allergies(session, patient["id"]),
    }


def list_chart_patients(*, session):
    patients = [_directory_entry(session, patient) for patient in list_patients(session)]
    patients.sort(key=lambda item: item["display_name"])
    return {"patients": patients}


def _series(session, patient_id):
    grouped = {}
    for observation in list_observations_by_patient(session, patient_id):
        name = observation["name"]
        bucket = grouped.setdefault(
            name,
            {
                "name": name,
                "unit": observation["unit"],
                "body_region_key": observation["body_region_key"],
                "points": [],
            },
        )
        bucket["points"].append(
            {
                "id": str(observation["id"]),
                "at": _zulu(observation["observed_at"]),
                "value": _whole_number(observation["value"]),
                "source": observation["source"],
                "document_id": observation["document_id"],
            }
        )
    series = []
    for item in grouped.values():
        item["points"].sort(key=lambda point: point["at"])
        series.append(item)
    series.sort(key=lambda item: item["name"])
    return series


def _focus_by_region(session):
    focus = {}
    for row in list_all_specialty_focus(session):
        focus.setdefault(row["region_key"], []).append(row["specialty_key"])
    for specialties in focus.values():
        specialties.sort()
    return focus


def get_chart(patient_id, *, session):
    """Everything the workspace needs for one patient, with real dates."""
    patient = get_patient(session, patient_id)
    if patient is None:
        return _error("not_found", "Patient was not found.")
    focus = _focus_by_region(session)
    rules = {str(row["id"]): row for row in list_reminder_rules(session)}
    coverage = get_coverage_by_patient(session, patient_id)
    pending = list_suggestions(session, patient_id, "pending")
    return {
        "patient": _directory_entry(session, patient),
        "regions": [
            {
                "region_key": row["region_key"],
                "display_name": row["display_name"],
                "mesh_name": row["mesh_name"],
                "specialties": focus.get(row["region_key"], []),
            }
            for row in list_body_regions(session)
        ],
        "conditions": [
            {
                "id": str(row["id"]),
                "name": row["name"],
                "status": row["status"],
                "onset_date": _date_string(row["onset_date"]),
                "body_region_key": row["body_region_key"],
            }
            for row in list_conditions_by_patient(session, patient_id)
        ],
        "medications": [
            {
                "id": str(row["id"]),
                "name": row["name"],
                "dose": row["dose"],
                "route": row["route"],
                "frequency": row["frequency"],
                "status": row["status"],
                "start_date": _date_string(row["start_date"]),
                "body_region_key": row["body_region_key"],
            }
            for row in list_medications_by_patient(session, patient_id)
        ],
        "series": _series(session, patient_id),
        "encounters": sorted(
            (
                {
                    "id": str(row["id"]),
                    "encounter_type": row["encounter_type"],
                    "occurred_at": _zulu(row["occurred_at"]),
                    "summary": row["summary"],
                }
                for row in list_encounters_by_patient(session, patient_id)
            ),
            key=lambda row: row["occurred_at"],
        ),
        "notes": sorted(
            (
                {
                    "id": str(row["id"]),
                    "body": row["body"],
                    "created_at": _zulu(row["created_at"]),
                    "source_suggestion_id": row["source_suggestion_id"],
                }
                for row in list_notes_by_patient(session, patient_id)
            ),
            key=lambda row: row["created_at"],
        ),
        "reminders": sorted(
            (
                {
                    "id": str(row["id"]),
                    "name": row["name"],
                    "due_on": _date_string(row["due_on"]),
                    "status": row["status"],
                    "rule": _rule_summary(rules.get(str(row["rule_id"]))),
                }
                for row in list_reminders_by_patient(session, patient_id)
            ),
            key=lambda row: (row["due_on"], row["name"]),
        ),
        "appointments": sorted(
            (
                {
                    "id": str(row["id"]),
                    "starts_at": _zulu(row["starts_at"]),
                    "ends_at": _zulu(row["ends_at"]),
                    "reason": row["reason"],
                    "status": row["status"],
                }
                for row in list_appointments_by_patient(session, patient_id)
            ),
            key=lambda row: row["starts_at"],
        ),
        "coverage": None
        if coverage is None
        else {
            "payer_name": coverage["payer_name"],
            "plan_name": coverage["plan_name"],
            "active": bool(coverage["active"]),
            "copay": _whole_number(coverage["copay"]),
            "deductible_remaining": _whole_number(coverage["deductible_remaining"]),
        },
        "pending_suggestions": len(pending),
    }


def _rule_summary(rule):
    if rule is None:
        return None
    return {
        "name": rule["name"],
        "baseline_age": rule["baseline_age"],
        "guideline_source_id": rule["guideline_source_id"],
    }


def get_body_state(patient_id, specialty, *, session):
    patient = get_patient(session, patient_id)
    if patient is None:
        return _error("not_found", "Patient was not found.")
    return {
        "patient": _patient_summary(patient),
        "specialty": specialty,
        "regions": _regions(session, patient_id, specialty),
        "timeline": _timeline(session, patient_id),
        "trends": _trends(session, patient_id),
    }


def get_region(patient_id, region_key, *, session):
    patient = get_patient(session, patient_id)
    if patient is None:
        return _error("not_found", "Patient was not found.")
    known = {row["region_key"] for row in list_body_regions(session)}
    if region_key not in known:
        return _error("not_found", "Region was not found.")
    return {
        "region_key": region_key,
        "conditions": list_conditions_by_region(session, patient_id, region_key),
        "medications": list_medications_by_region(session, patient_id, region_key),
        "observations": list_observations_by_region(session, patient_id, region_key),
    }
