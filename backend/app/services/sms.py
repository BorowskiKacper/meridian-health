from app.db.repositories import (
    get_sms_message_by_sid,
    list_patients,
    update_patient,
    update_sms_message,
)

_WHATSAPP_PREFIX = "whatsapp:"


def _phone_from_sender(sender):
    text = str(sender)
    if text.casefold().startswith(_WHATSAPP_PREFIX):
        return text[len(_WHATSAPP_PREFIX) :]
    return text


def send_whatsapp(from_number, to, body):
    import app.config as config
    from twilio.rest import Client

    client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
    message = client.messages.create(from_=from_number, to=to, body=body)
    return message.sid


def handle_sms_webhook(form, *, session):
    if form["Body"].strip().casefold() == "stop":
        phone = _phone_from_sender(form["From"])
        for patient in list_patients(session):
            if patient["phone_e164"] == phone:
                update_patient(session, patient["id"], {"sms_opt_in": False})
                break
    row = get_sms_message_by_sid(session, form["MessageSid"])
    if row is not None:
        update_sms_message(session, row["id"], {"status": form["MessageStatus"]})
    return None
