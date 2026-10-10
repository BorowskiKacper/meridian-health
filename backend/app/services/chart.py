from datetime import date, datetime, timezone

from app.db.repositories import (
    get_patient,
    list_body_regions,
    list_conditions_by_patient,
    list_conditions_by_region,
    list_encounters_by_patient,
    list_family_history_by_patient,
    list_medications_by_patient,
    list_medications_by_region,
    list_observations_by_patient,
    list_observations_by_region,
    list_patients,
    list_specialty_focus,
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


def list_chart_patients(*, session):
    patients = []
    for patient in list_patients(session):
        family = [
            {
                "relationship": row["relationship"],
                "condition": row["condition"],
                "age_at_diagnosis": row["age_at_diagnosis"],
            }
            for row in list_family_history_by_patient(session, patient["id"])
        ]
        patients.append(
            {
                "id": str(patient["id"]),
                "display_name": patient["display_name"],
                "age": _age(patient["date_of_birth"]),
                "sex": patient["sex"],
                "sms_opt_in": bool(patient["sms_opt_in"]),
                "phone_e164": patient["phone_e164"],
                "family_history": family,
            }
        )
    patients.sort(key=lambda item: item["display_name"])
    return {"patients": patients}


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
