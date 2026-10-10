import importlib
import inspect
from pathlib import Path

from starlette.routing import Match

from app.main import app

JANE_ID = "11111111-1111-4111-8111-111111111111"
JOHN_ID = "22222222-2222-4222-8222-222222222222"
AMY_ID = "33333333-3333-4333-8333-333333333333"
UNKNOWN_ID = "44444444-4444-4444-8444-444444444444"

SECRETARY = {"X-Role": "secretary"}
DOCTOR = {"X-Role": "doctor"}

REPO_ROOT = Path(__file__).resolve().parents[3]


def bind_session(monkeypatch, session):
    import importlib

    try:
        db = importlib.import_module("app.api.db")
    except ModuleNotFoundError:
        return
    monkeypatch.setattr(db, "get_session", lambda: session)


def assert_error(response, status, code):
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error"}
    error = body["error"]
    assert set(error) == {"code", "message"}
    assert error["code"] == code
    assert isinstance(error["message"], str)
    assert error["message"].strip()


def listed_ids(items):
    found = []
    for item in items:
        if isinstance(item, dict):
            found.append(str(item["id"]))
        else:
            found.append(str(item))
    return found


def _is_unimplemented(endpoint):
    try:
        source = inspect.getsource(endpoint)
    except (OSError, TypeError):
        return False
    body = []
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("@", "def ", "async def ")):
            continue
        body.append(stripped)
    return body == ["raise NotImplementedError"]


def _unimplemented_route(path, method):
    scope = {"type": "http", "path": path, "method": method.upper()}
    for route in app.routes:
        endpoint = getattr(route, "endpoint", None)
        if endpoint is None or not _is_unimplemented(endpoint):
            continue
        match, _child = route.matches(scope)
        if match == Match.FULL:
            return route
    return None


def _raise_unimplemented(route):
    args = []
    kwargs = {}
    signature = inspect.signature(route.endpoint)
    for name, param in signature.parameters.items():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        if param.default is not inspect.Parameter.empty:
            continue
        if param.kind is inspect.Parameter.POSITIONAL_ONLY:
            args.append("stub")
        else:
            kwargs[name] = "stub"
    route.endpoint(*args, **kwargs)


def call(client, method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    # Stubs declare required query params, so a contract body is a 422 before
    # the handler. Enter the handler so the missing route still raises.
    route = _unimplemented_route(path, method)
    if response.status_code == 422 and route is not None:
        _raise_unimplemented(route)
    return response


def install_secretary_model(monkeypatch, complete):
    import sys
    import types

    name = "app.agents.secretary.model"
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        module = types.ModuleType(name)
        module.__package__ = "app.agents.secretary"
        monkeypatch.setitem(sys.modules, name, module)
        import app.agents.secretary as secretary

        monkeypatch.setattr(secretary, "model", module, raising=False)
    monkeypatch.setattr(name + ".complete", complete, raising=False)
