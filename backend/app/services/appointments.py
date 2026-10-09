def list_appointments(patient_id, on):
    raise NotImplementedError


def create_appointment(patient_id, starts_at, ends_at, reason):
    raise NotImplementedError


def update_appointment(
    appointment_id, starts_at=None, ends_at=None, reason=None, status=None
):
    raise NotImplementedError
