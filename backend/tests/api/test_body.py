from api_support import JANE_ID, JOHN_ID, UNKNOWN_ID, assert_error, bind_session, call

BODY_KEYS = {"patient", "specialty", "regions", "timeline", "trends"}


def test_list_patients_includes_the_seeded_chart(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)

    response = call(client, "GET", "/patients")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"patients"}
    jane = next(item for item in body["patients"] if item["id"] == JANE_ID)
    assert jane["display_name"] == "Jane Doe"
    assert jane["sex"] == "female"
    assert jane["sms_opt_in"] is True
    assert jane["phone_e164"] == "+15555550101"
    assert {
        "relationship": "father",
        "condition": "colorectal cancer",
        "age_at_diagnosis": 48,
    } in jane["family_history"]


def test_list_patients_includes_allergies(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)

    response = call(client, "GET", "/patients")

    assert response.status_code == 200
    jane = next(item for item in response.json()["patients"] if item["id"] == JANE_ID)
    assert jane["date_of_birth"] == "1974-03-15"
    substances = [row["substance"] for row in jane["allergies"]]
    # Sorted by severity so the banner shows the dangerous one first.
    assert substances == ["Shellfish", "Penicillin"]
    shellfish = jane["allergies"][0]
    assert shellfish["severity"] == "severe"
    assert shellfish["reaction"] == "Lip swelling"
    assert shellfish["category"] == "food"
    assert shellfish["recorded_on"] == "2015-02-03"
    john = next(item for item in response.json()["patients"] if item["id"] == JOHN_ID)
    assert [row["category"] for row in john["allergies"]] == ["nkda"]


CHART_KEYS = {
    "patient",
    "regions",
    "conditions",
    "medications",
    "series",
    "encounters",
    "notes",
    "reminders",
    "appointments",
    "coverage",
    "pending_suggestions",
}


def test_chart_returns_jane_with_real_dates(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)

    response = call(client, "GET", f"/patients/{JANE_ID}/chart")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == CHART_KEYS
    assert body["patient"]["id"] == JANE_ID
    assert body["patient"]["allergies"][0]["substance"] == "Shellfish"

    heart = next(region for region in body["regions"] if region["region_key"] == "heart")
    assert heart["mesh_name"] == "Heart"
    assert "cardiology" in heart["specialties"]

    hypertension = next(row for row in body["conditions"] if row["name"] == "Hypertension")
    assert hypertension["status"] == "active"
    assert hypertension["onset_date"] == "2019-04-01"
    assert hypertension["body_region_key"] == "heart"

    lisinopril = next(row for row in body["medications"] if row["name"] == "Lisinopril")
    assert lisinopril["start_date"] == "2019-04-02"
    assert lisinopril["dose"] == "10 mg"

    ldl = next(series for series in body["series"] if series["name"] == "LDL")
    assert ldl["unit"] == "mg/dL"
    assert ldl["body_region_key"] == "heart"
    assert ldl["points"] == [
        {
            "id": ldl["points"][0]["id"],
            "at": "2024-03-01T00:00:00Z",
            "value": 140,
            "source": "seed",
            "document_id": None,
        }
    ]

    colonoscopy = next(row for row in body["encounters"] if row["encounter_type"] == "procedure")
    assert colonoscopy["occurred_at"] == "2024-06-01T15:00:00Z"
    assert body["notes"][0]["created_at"] == "2024-03-01T12:00:00Z"

    screening = next(row for row in body["reminders"] if row["name"] == "Colorectal cancer screening")
    assert screening["due_on"] == "2026-10-01"
    assert screening["status"] == "scheduled"
    assert screening["rule"] == {
        "name": "Colorectal cancer screening",
        "baseline_age": 45,
        "guideline_source_id": "uspstf:colorectal-cancer-screening",
    }

    assert body["appointments"][0]["starts_at"] == "2026-10-10T15:00:00Z"
    assert body["coverage"] == {
        "payer_name": "Northwind Health",
        "plan_name": "PPO",
        "active": True,
        "copay": 30,
        "deductible_remaining": 400,
    }
    assert body["pending_suggestions"] == 0


def test_chart_unknown_patient_is_not_found(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)

    response = call(client, "GET", f"/patients/{UNKNOWN_ID}/chart")

    assert_error(response, 404, "not_found")


def test_body_state_returns_jane_for_cardiology(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)

    response = call(
        client,
        "GET",
        f"/patients/{JANE_ID}/body-state",
        params={"specialty": "cardiology"},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == BODY_KEYS
    assert body["patient"]["display_name"] == "Jane Doe"
    assert body["specialty"] == "cardiology"


def test_body_state_unknown_patient_is_not_found(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)

    response = call(
        client,
        "GET",
        f"/patients/{UNKNOWN_ID}/body-state",
        params={"specialty": "cardiology"},
    )

    assert_error(response, 404, "not_found")


def test_body_state_missing_specialty_is_validation_error(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)

    response = call(client, "GET", f"/patients/{JANE_ID}/body-state")

    assert_error(response, 400, "validation_error")


def test_heart_region_returns_region_key(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)

    response = call(client, "GET", f"/patients/{JANE_ID}/regions/heart")

    assert response.status_code == 200
    body = response.json()
    assert body["region_key"] == "heart"


def test_unknown_region_is_not_found(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)

    response = call(client, "GET", f"/patients/{JANE_ID}/regions/spleen")

    assert_error(response, 404, "not_found")
