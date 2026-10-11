import hashlib
import hmac
import uuid

import httpx

from app import config
from app.db.repositories import get_patient, update_patient
from app.integrations import IntegrationError

_RESEND_URL = "https://api.resend.com/emails"
_SUBJECT = "Clinic reminder"
_CONFIRMATION = "You are unsubscribed from clinic reminders."


def unsubscribe_token(patient_id):
    patient_id = str(patient_id)
    signature = hmac.new(
        config.EMAIL_UNSUBSCRIBE_SECRET.encode("utf-8"),
        patient_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{patient_id}.{signature}"


def patient_id_from_token(token):
    text = "" if token is None else str(token)
    patient_id, separator, signature = text.partition(".")
    if separator != "." or not patient_id or not signature:
        return None
    expected = unsubscribe_token(patient_id).split(".", 1)[1]
    if len(signature) != len(expected) or not hmac.compare_digest(signature, expected):
        return None
    return patient_id


def unsubscribe_link(patient_id):
    base = config.EMAIL_PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/email/unsubscribe?token={unsubscribe_token(patient_id)}"


def send_email(to_email, body):
    if not config.RESEND_API_KEY:
        raise IntegrationError("Resend", "Email is not configured on the server.")
    try:
        response = httpx.post(
            _RESEND_URL,
            headers={
                "Authorization": f"Bearer {config.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": config.EMAIL_FROM,
                "to": [to_email],
                "subject": _SUBJECT,
                "text": body,
            },
            timeout=30,
        )
        response.raise_for_status()
        message_id = response.json().get("id")
    except IntegrationError:
        raise
    except Exception:
        raise IntegrationError(
            "Resend",
            "The email service did not accept this reminder.",
        ) from None
    if not isinstance(message_id, str) or not message_id.strip():
        raise IntegrationError("Resend", "The email service did not accept this reminder.")
    return message_id


def unsubscribe(token, *, session):
    patient_id = patient_id_from_token(token)
    if patient_id is None:
        return None
    try:
        uuid.UUID(patient_id)
    except ValueError:
        return None
    patient = get_patient(session, patient_id)
    if patient is None:
        return None
    if patient["email_opt_in"] is not False:
        update_patient(session, patient_id, {"email_opt_in": False})
    return _CONFIRMATION
