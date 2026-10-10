from app.db.repositories import get_patient
from support import JANE_ID, bind_session, call


def test_stop_webhook_opts_jane_out(seeded_db, monkeypatch, client):
    bind_session(monkeypatch, seeded_db.session)

    response = call(
        client,
        "POST",
        "/webhooks/twilio",
        data={
            "MessageSid": "SM123",
            "MessageStatus": "received",
            "From": "whatsapp:+15555550101",
            "Body": " STOP ",
        },
    )

    assert response.status_code == 200
    assert response.content == b""
    assert get_patient(seeded_db.session, JANE_ID)["sms_opt_in"] is False
