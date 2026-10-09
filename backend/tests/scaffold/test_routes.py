"""app.main exposes the skeleton HTTP routes."""

import importlib

import pytest

# Trailing-slash aliases are optional. Other routes may also be registered.
REQUIRED_ROUTES = frozenset(
    {
        ("GET", "/patients/{patient_id}/body-state"),
        ("GET", "/patients/{patient_id}/regions/{region_key}"),
        ("POST", "/requests"),
        ("GET", "/suggestions"),
        ("POST", "/suggestions"),
        ("POST", "/suggestions/approve"),
        ("POST", "/suggestions/reject"),
        ("POST", "/documents"),
        ("PUT", "/patients/{patient_id}/reminders/{reminder_id}"),
        ("POST", "/demo/run-reminders"),
        ("POST", "/patients/{patient_id}/eligibility"),
        ("GET", "/appointments"),
        ("POST", "/appointments"),
        ("PUT", "/appointments/{appointment_id}"),
        ("POST", "/secretary/requests"),
        ("POST", "/webhooks/twilio"),
    }
)


def iter_routes(routes):
    for route in routes:
        nested = getattr(route, "routes", None)
        if nested:
            yield from iter_routes(nested)
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if methods and path is not None:
            yield methods, path


def test_main_app_includes_required_routes():
    try:
        main = importlib.import_module("app.main")
    except Exception as exc:
        pytest.fail(f"import app.main failed: {exc.__class__.__name__}: {exc}")
    try:
        fastapi = importlib.import_module("fastapi")
    except Exception as exc:
        pytest.fail(f"import fastapi failed: {exc.__class__.__name__}: {exc}")

    assert hasattr(main, "app"), "app.main.app is missing"
    app = main.app
    assert isinstance(app, fastapi.FastAPI)

    found = set()
    for methods, path in iter_routes(app.routes):
        for method in methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            found.add((method.upper(), path))

    missing = REQUIRED_ROUTES - found
    rendered = "\n".join(f"{method} {path}" for method, path in sorted(missing))
    assert not missing, f"missing routes:\n{rendered}"
