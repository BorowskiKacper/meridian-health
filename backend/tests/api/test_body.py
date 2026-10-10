from api_support import JANE_ID, UNKNOWN_ID, assert_error, bind_session, call

BODY_KEYS = {"patient", "specialty", "regions", "timeline", "trends"}


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
