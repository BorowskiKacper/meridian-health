"""Public skeleton callables raise NotImplementedError when called."""

import asyncio
import importlib
import importlib.util
import inspect
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]

STUBS = [
    ("app.agents.doctor", "route_doctor_request", ("p", "t", "typed")),
    ("app.agents.doctor", "run_reminder_agent", ("p", "doctor_request")),
    ("app.agents.doctor.verify", "verify_claims", ("t", [])),
    ("app.agents.secretary", "answer_secretary", ("p", "t")),
    ("app.services.approval", "approve_suggestions", ([], {})),
    ("app.services.approval", "reject_suggestions", ([], "r")),
    ("app.services.approval", "list_suggestions", ("p", "pending")),
    ("app.services.approval", "create_plan_item", ("p", "r", "t", [])),
    ("app.services.labs", "extract_lab_report", ("p", b"", "image/jpeg")),
    ("app.services.eligibility", "check_eligibility", ("p", None)),
    ("app.services.reminders", "send_due_reminders", (None,)),
    ("app.services.reminders", "update_reminder", ("p", "r", None, None)),
    ("app.services.sms", "handle_sms_webhook", ({},)),
    ("app.services.chart", "get_body_state", ("p", "cardiology")),
    ("app.services.chart", "get_region", ("p", "heart")),
    ("app.services.appointments", "list_appointments", ("p", None)),
    (
        "app.services.appointments",
        "create_appointment",
        ("p", "2026-10-10T15:00:00Z", "2026-10-10T15:30:00Z", "Follow-up"),
    ),
    ("app.services.appointments", "update_appointment", ("a",)),
    ("app.mcp.tools", "get_patient_context", ("p",)),
    ("app.mcp.tools", "search_patient_notes", ("p", "ldl")),
    ("app.mcp.tools", "get_coverage", ("p",)),
    ("app.mcp.tools", "propose_change", ("p", {})),
    ("app.evidence", "search_guidelines", ("t", "uspstf")),
    ("app.evidence", "search_medical_web", ("t",)),
    ("app.evidence", "search_payer_docs", ("t",)),
    ("app.evidence", "web_search", ("t",)),
    ("app.api.routes.body", "get_body_state", ("p", "cardiology")),
    ("app.api.routes.body", "get_region", ("p", "heart")),
    ("app.api.routes.requests", "create_request", ("p",)),
    ("app.api.routes.suggestions", "list_suggestions", ("p",)),
    ("app.api.routes.suggestions", "create_suggestion", ("p", "r", "t", [])),
    ("app.api.routes.suggestions", "approve", ([],)),
    ("app.api.routes.suggestions", "reject", ([], "reason")),
    ("app.api.routes.documents", "upload_document", ("p", b"", "image/jpeg")),
    ("app.api.routes.reminders", "update_reminder", ("p", "r")),
    ("app.api.routes.reminders", "run_reminders", ()),
    ("app.api.routes.eligibility", "check_eligibility", ("p",)),
    ("app.api.routes.appointments", "list_appointments", ()),
    (
        "app.api.routes.appointments",
        "create_appointment",
        ("p", "2026-10-10T15:00:00Z", "2026-10-10T15:30:00Z", "Follow-up"),
    ),
    ("app.api.routes.appointments", "update_appointment", ("a",)),
    ("app.api.routes.secretary", "create_secretary_request", ("p", "t")),
    ("app.api.routes.webhooks", "twilio_webhook", ({},)),
]


def invoke(fn, args):
    fresh = []
    for arg in args:
        if isinstance(arg, (list, dict)):
            fresh.append(arg.copy())
        else:
            fresh.append(arg)
    result = fn(*fresh)
    if inspect.iscoroutine(result):
        return asyncio.run(result)
    return result


def load_seed_module():
    seed_path = BACKEND_DIR / "seed" / "seed.py"
    if not seed_path.is_file():
        pytest.fail(f"missing {seed_path}")
    spec = importlib.util.spec_from_file_location("seed", seed_path)
    if spec is None or spec.loader is None:
        pytest.fail(f"could not load {seed_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("module_name", "func_name", "args"),
    STUBS,
    ids=[f"{module_name}.{func_name}" for module_name, func_name, _args in STUBS],
)
def test_stub_raises_not_implemented(module_name, func_name, args):
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        pytest.fail(f"import {module_name} failed: {exc.__class__.__name__}: {exc}")
    fn = getattr(module, func_name, None)
    if not callable(fn):
        pytest.fail(f"{module_name}.{func_name} is missing")
    with pytest.raises(NotImplementedError):
        invoke(fn, args)


def test_speech_hook_transcribe_and_synthesize_raise_not_implemented():
    try:
        hook_mod = importlib.import_module("app.speech.hook")
    except Exception as exc:
        pytest.fail(f"import app.speech.hook failed: {exc.__class__.__name__}: {exc}")
    speech_hook_type = getattr(hook_mod, "SpeechHook", None)
    if not callable(speech_hook_type):
        pytest.fail("app.speech.hook.SpeechHook is missing")
    hook = speech_hook_type()
    with pytest.raises(NotImplementedError):
        invoke(hook.transcribe, (b"",))
    with pytest.raises(NotImplementedError):
        invoke(hook.synthesize, ("hello",))


def test_seed_raises_not_implemented():
    module = load_seed_module()
    seed = getattr(module, "seed", None)
    if not callable(seed):
        pytest.fail("backend/seed/seed.py must expose a callable seed")
    with pytest.raises(NotImplementedError):
        invoke(seed, ())
