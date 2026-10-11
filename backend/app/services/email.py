import hashlib
import hmac
import html
import uuid
from datetime import date, datetime

import httpx

from app import config
from app.db.repositories import get_patient, update_patient
from app.integrations import IntegrationError

_RESEND_URL = "https://api.resend.com/emails"
_CONFIRMATION = "You are unsubscribed from clinic reminders."
_TEMPLATE_KEYS = ("PATIENT_NAME", "REMINDER_NAME", "DUE_ON", "UNSUBSCRIBE_URL")


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


def format_due(value):
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return f"{value.strftime('%B')} {value.day}, {value.year}"
    return str(value)[:10]


def reminder_text(patient_name, reminder_name, due_on, unsubscribe_url):
    return (
        f"Hello {patient_name},\n"
        f"You have a clinic reminder: {reminder_name}. "
        f"It is due on {format_due(due_on)}. "
        "Please contact the office to schedule a visit.\n"
        f"{unsubscribe_url}"
    )


def template_variables(patient_name, reminder_name, due_on, unsubscribe_url):
    values = {
        "PATIENT_NAME": patient_name,
        "REMINDER_NAME": reminder_name,
        "DUE_ON": format_due(due_on),
        "UNSUBSCRIBE_URL": unsubscribe_url,
    }
    return {key: html.escape(str(values[key]), quote=True) for key in _TEMPLATE_KEYS}


def send_email(to_email, variables):
    if not config.RESEND_API_KEY:
        raise IntegrationError("Resend", "Email is not configured on the server.")
    template_id = config.EMAIL_TEMPLATE_ID.strip()
    if not template_id:
        raise IntegrationError("Resend", "The email template is not configured on the server.")
    if not isinstance(variables, dict) or any(
        not isinstance(variables.get(key), str) or not variables[key].strip()
        for key in _TEMPLATE_KEYS
    ):
        raise IntegrationError("Resend", "The email service did not accept this reminder.")
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
                "template": {
                    "id": template_id,
                    "variables": {key: variables[key] for key in _TEMPLATE_KEYS},
                },
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
