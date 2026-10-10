"""The HTTP handlers ask this module for the request's database session."""

from contextlib import contextmanager


@contextmanager
def get_session():
    from app.runtime import current_session

    session = current_session()
    if session is not None:
        # The HTTP middleware owns this transaction and closes it after the response.
        yield session
    else:
        from app.sessions import open_session

        with open_session() as session:
            yield session


def tests_replaced_session():
    return get_session.__module__ != __name__
