def approve_suggestions(ids, edits):
    raise NotImplementedError


def reject_suggestions(ids, reason):
    raise NotImplementedError


def list_suggestions(patient_id, status):
    raise NotImplementedError


def create_plan_item(patient_id, request_id, text, citations):
    raise NotImplementedError
