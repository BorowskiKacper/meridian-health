import pytest

from support import DOCTOR, JANE_ID, SECRETARY, UNKNOWN_ID, assert_error, bind_session, call

SUMMARY = "Coverage is active."


def _install_model(monkeypatch):
    def ask_model(prompt):
        return {
            "summary": SUMMARY,
            "prior_auth_required": False,
            "prior_auth_note": "",
        }

    monkeypatch.setattr("app.services.eligibility.ask_model", ask_model)


@pytest.mark.parametrize("headers", [DOCTOR, SECRETARY, None])
def test_eligibility_for_doctor_and_secretary(seeded_db, monkeypatch, client, headers):
    bind_session(monkeypatch, seeded_db.session)
    _install_model(monkeypatch)
    kwargs = {
        "json": {"order_text": "screening colonoscopy"},
    }
    if headers is not None:
        kwargs["headers"] = headers

    response = call(client, "POST", f"/patients/{JANE_ID}/eligibility", **kwargs)

    assert response.status_code == 200
    body = response.json()
    assert body["coverage"]["member_id"] == "NW-1001"
    assert body["prior_auth"] is None
    assert body["summary"] == SUMMARY


def test_eligibility_unknown_patient_is_not_found(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)
    _install_model(monkeypatch)

    response = call(
        client,
        "POST",
        f"/patients/{UNKNOWN_ID}/eligibility",
        json={"order_text": "screening colonoscopy"},
    )

    assert_error(response, 404, "not_found")
