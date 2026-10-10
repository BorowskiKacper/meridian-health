import re
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.db.repositories import (
    get_patient,
    insert_condition,
    list_body_regions,
    list_conditions_by_region,
    list_medications_by_region,
    list_observations_by_region,
    list_specialty_focus,
)
from app.services.chart import get_body_state, get_region

JANE_ID = "11111111-1111-4111-8111-111111111111"
AMY_ID = "33333333-3333-4333-8333-333333333333"
JANE_DOB = date(1974, 3, 15)
UNKNOWN_PATIENT_ID = "99999999-9999-4999-8999-999999999999"

ZULU = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
TIMELINE_KINDS = {"condition", "medication", "encounter"}
REGION_KEYS = {"region_key", "mesh_name", "emphasis", "pulse", "condition_count"}
BODY_KEYS = {"patient", "specialty", "regions", "timeline", "trends"}
REGION_RESPONSE_KEYS = {"region_key", "conditions", "medications", "observations"}

JANE_TIMELINE = [
    {"at": "2019-04-01T00:00:00Z", "kind": "condition", "label": "Hypertension"},
    {"at": "2019-04-02T00:00:00Z", "kind": "medication", "label": "Lisinopril"},
    {
        "at": "2024-06-01T15:00:00Z",
        "kind": "encounter",
        "label": "Screening colonoscopy",
    },
]
OLD_COUGH = {
    "at": "2020-01-01T00:00:00Z",
    "kind": "condition",
    "label": "Old cough",
}
LDL_TREND = {
    "name": "LDL",
    "unit": "mg/dL",
    "points": [{"at": "2024-03-01T00:00:00Z", "value": 140}],
}


def invoke(fn, *args, session, **kwargs):
    import inspect

    if "session" in inspect.signature(fn).parameters:
        kwargs["session"] = session
    return fn(*args, **kwargs)


def age_years(dob):
    today = datetime.now(timezone.utc).date()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def assert_error(body, code, message_contains=None):
    assert isinstance(body, dict)
    assert set(body) == {"error"}
    error = body["error"]
    assert isinstance(error, dict)
    assert set(error) == {"code", "message"}
    assert error["code"] == code
    assert isinstance(error["message"], str)
    assert error["message"].strip()
    if message_contains is not None:
        assert message_contains in error["message"]


def assert_patient(body, patient_id, display_name, dob):
    assert set(body["patient"]) == {"id", "display_name", "age"}
    assert body["patient"]["id"] == patient_id
    assert body["patient"]["display_name"] == display_name
    age = body["patient"]["age"]
    assert isinstance(age, int) and not isinstance(age, bool)
    assert age == age_years(dob)


def assert_regions(body, session, patient_id, specialty):
    catalog = list_body_regions(session)
    focused = {
        row["region_key"] for row in list_specialty_focus(session, specialty)
    }
    mesh_names = {row["region_key"]: row["mesh_name"] for row in catalog}
    assert isinstance(body["regions"], list)
    seen = {}
    for region in body["regions"]:
        assert set(region) == REGION_KEYS
        key = region["region_key"]
        assert key not in seen
        seen[key] = region
        conditions = list_conditions_by_region(session, patient_id, key)
        emphasis = "focus" if key in focused else "dim"
        pulse = emphasis == "focus" and any(
            row["status"] == "active" for row in conditions
        )
        assert region["mesh_name"] == mesh_names[key]
        assert region["emphasis"] == emphasis
        assert region["pulse"] is pulse
        count = region["condition_count"]
        assert isinstance(count, int) and not isinstance(count, bool)
        assert count == len(conditions)
    assert set(seen) == set(mesh_names)
    return seen


def assert_timeline_shape(timeline):
    assert isinstance(timeline, list)
    instants = []
    for item in timeline:
        assert set(item) == {"at", "kind", "label"}
        assert item["kind"] in TIMELINE_KINDS
        assert isinstance(item["label"], str) and item["label"]
        assert ZULU.fullmatch(item["at"])
        instants.append(item["at"])
    assert instants == sorted(instants)


def assert_timeline(timeline, expected):
    assert_timeline_shape(timeline)
    assert timeline == expected


def assert_trend_shape(trends):
    assert isinstance(trends, list)
    for trend in trends:
        assert set(trend) == {"name", "unit", "points"}
        assert isinstance(trend["name"], str) and trend["name"]
        assert isinstance(trend["unit"], str) and trend["unit"]
        assert isinstance(trend["points"], list)
        point_instants = []
        for point in trend["points"]:
            assert set(point) == {"at", "value"}
            assert ZULU.fullmatch(point["at"])
            assert isinstance(point["value"], (int, float))
            assert not isinstance(point["value"], bool)
            point_instants.append(point["at"])
        assert point_instants == sorted(point_instants)


def assert_jane_body(body, session, specialty, timeline):
    assert isinstance(body, dict)
    assert set(body) == BODY_KEYS
    assert body["specialty"] == specialty
    assert_patient(body, JANE_ID, "Jane Doe", JANE_DOB)
    regions = assert_regions(body, session, JANE_ID, specialty)
    assert_timeline(body["timeline"], timeline)
    assert_trend_shape(body["trends"])
    assert body["trends"] == [LDL_TREND]
    return regions


def test_get_body_state_jane_cardiology(seeded_db):
    session = seeded_db.session
    body = invoke(get_body_state, JANE_ID, "cardiology", session=session)

    regions = assert_jane_body(body, session, "cardiology", JANE_TIMELINE)
    assert regions["heart"] == {
        "region_key": "heart",
        "mesh_name": "Heart",
        "emphasis": "focus",
        "pulse": True,
        "condition_count": 1,
    }
    assert regions["lung"] == {
        "region_key": "lung",
        "mesh_name": "Lung",
        "emphasis": "dim",
        "pulse": False,
        "condition_count": 0,
    }
    assert regions["colon"] == {
        "region_key": "colon",
        "mesh_name": "Colon",
        "emphasis": "dim",
        "pulse": False,
        "condition_count": 0,
    }


def test_get_body_state_jane_gastroenterology_dims_heart(seeded_db):
    session = seeded_db.session
    body = invoke(get_body_state, JANE_ID, "gastroenterology", session=session)

    regions = assert_jane_body(body, session, "gastroenterology", JANE_TIMELINE)
    assert regions["colon"]["emphasis"] == "focus"
    assert regions["colon"]["pulse"] is False
    assert regions["colon"]["condition_count"] == 0
    assert regions["colon"]["mesh_name"] == "Colon"
    assert regions["heart"] == {
        "region_key": "heart",
        "mesh_name": "Heart",
        "emphasis": "dim",
        "pulse": False,
        "condition_count": 1,
    }


def test_get_body_state_amy_gastroenterology_pulses_colon(seeded_db):
    session = seeded_db.session
    body = invoke(get_body_state, AMY_ID, "gastroenterology", session=session)

    assert isinstance(body, dict)
    assert set(body) == BODY_KEYS
    assert body["specialty"] == "gastroenterology"
    amy = get_patient(session, AMY_ID)
    assert_patient(body, AMY_ID, "Amy Lee", amy["date_of_birth"])
    regions = assert_regions(body, session, AMY_ID, "gastroenterology")
    assert regions["colon"] == {
        "region_key": "colon",
        "mesh_name": "Colon",
        "emphasis": "focus",
        "pulse": True,
        "condition_count": 1,
    }
    assert_timeline_shape(body["timeline"])
    assert {item["kind"] for item in body["timeline"]} >= {"condition", "medication"}
    assert any(
        item["kind"] == "condition" and item["label"] == "Diverticulosis"
        for item in body["timeline"]
    )
    assert all(item["label"] != "Hypertension" for item in body["timeline"])
    assert_trend_shape(body["trends"])


def test_get_body_state_unknown_specialty_dims_every_region(seeded_db):
    session = seeded_db.session
    body = invoke(get_body_state, JANE_ID, "dermatology", session=session)

    regions = assert_jane_body(body, session, "dermatology", JANE_TIMELINE)
    assert regions
    for region in regions.values():
        assert region["emphasis"] == "dim"
        assert region["pulse"] is False
    assert regions["heart"]["condition_count"] == 1
    assert regions["heart"]["mesh_name"] == "Heart"


def test_get_body_state_resolved_condition_does_not_pulse(seeded_db):
    session = seeded_db.session
    insert_condition(
        session,
        {
            "id": str(uuid4()),
            "patient_id": JANE_ID,
            "name": "Old cough",
            "status": "resolved",
            "onset_date": date(2020, 1, 1),
            "body_region_key": "lung",
        },
    )
    body = invoke(get_body_state, JANE_ID, "pulmonology", session=session)

    timeline = [
        JANE_TIMELINE[0],
        JANE_TIMELINE[1],
        OLD_COUGH,
        JANE_TIMELINE[2],
    ]
    regions = assert_jane_body(body, session, "pulmonology", timeline)
    assert regions["lung"] == {
        "region_key": "lung",
        "mesh_name": "Lung",
        "emphasis": "focus",
        "pulse": False,
        "condition_count": 1,
    }


def test_get_body_state_unknown_patient(seeded_db):
    body = invoke(
        get_body_state,
        UNKNOWN_PATIENT_ID,
        "cardiology",
        session=seeded_db.session,
    )

    assert_error(body, "not_found", "Patient")


def _names(rows):
    assert isinstance(rows, list)
    names = []
    for row in rows:
        assert isinstance(row, dict)
        assert isinstance(row["name"], str) and row["name"]
        names.append(row["name"])
    return names


def _assert_same_names(actual, stored):
    assert sorted(_names(actual)) == sorted(_names(stored))
    assert len(actual) == len(stored)


def test_get_region_jane_heart(seeded_db):
    session = seeded_db.session
    body = invoke(get_region, JANE_ID, "heart", session=session)

    assert set(body) == REGION_RESPONSE_KEYS
    assert body["region_key"] == "heart"
    _assert_same_names(
        body["conditions"],
        list_conditions_by_region(session, JANE_ID, "heart"),
    )
    _assert_same_names(
        body["medications"],
        list_medications_by_region(session, JANE_ID, "heart"),
    )
    _assert_same_names(
        body["observations"],
        list_observations_by_region(session, JANE_ID, "heart"),
    )
    assert len(body["conditions"]) == 1
    hypertension = body["conditions"][0]
    assert hypertension["name"] == "Hypertension"
    assert hypertension["status"] == "active"
    assert len(body["medications"]) == 1
    assert body["medications"][0]["name"] == "Lisinopril"
    assert len(body["observations"]) == 1
    ldl = body["observations"][0]
    assert ldl["name"] == "LDL"
    assert ldl["value"] == 140
    assert ldl["unit"] == "mg/dL"


def test_get_region_jane_lung_is_empty(seeded_db):
    body = invoke(get_region, JANE_ID, "lung", session=seeded_db.session)

    assert set(body) == REGION_RESPONSE_KEYS
    assert body["region_key"] == "lung"
    assert body["conditions"] == []
    assert body["medications"] == []
    assert body["observations"] == []


def test_get_region_unknown_region(seeded_db):
    body = invoke(get_region, JANE_ID, "spleen", session=seeded_db.session)

    assert_error(body, "not_found", "Region")


def test_get_region_unknown_patient(seeded_db):
    body = invoke(get_region, UNKNOWN_PATIENT_ID, "heart", session=seeded_db.session)

    assert_error(body, "not_found", "Patient")


def test_chart_and_appointment_services_do_not_reference_agents():
    root = Path(__file__).resolve().parents[3]
    services = root / "backend" / "app" / "services"
    for name in ("chart.py", "appointments.py"):
        text = (services / name).read_text(encoding="utf-8")
        assert "app.agents" not in text
