"""The HTTP handlers ask this module for the request's database session."""


def get_session():
    from app.runtime import current_session

    session = current_session()
    if session is None:
        raise RuntimeError("No database session is bound.")
    return session


def tests_replaced_session():
    return get_session.__module__ != __name__
