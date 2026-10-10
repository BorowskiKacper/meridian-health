from api_support import JANE_ID, UNKNOWN_ID, assert_error, bind_session, call

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
