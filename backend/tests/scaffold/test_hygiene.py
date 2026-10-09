"""Repo hygiene for the skeleton: ignore rules, secrets, dependencies, and stub imports."""

import ast
import re
import subprocess
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"

REQUIRED_RUNTIME = {
    "fastapi",
    "uvicorn",
    "python-multipart",
    "pydantic",
    "python-dotenv",
    "sqlalchemy",
    "psycopg",
    "pgvector",
    "httpx",
    "google-genai",
    "twilio",
}

FORBIDDEN_MODULES = (
    "sqlalchemy",
    "psycopg",
    "httpx",
    "google.genai",
    "google.generativeai",
    "twilio",
)

MARKER_NAMES = ("API_KEY", "ACCOUNT_SID", "PASSWORD", "SECRET", "TOKEN")
ASSIGNMENT = re.compile(
    r"(?:^|[\s;])(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=(?!=)\s*(?P<value>[^\n]*)"
)
REQUIREMENT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")


def active_gitignore_lines(text):
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def is_dotenv_pattern(line):
    if line.startswith("!"):
        return False
    return line in {".env", "/.env", "**/.env", "*.env"} or line.endswith("/.env")


def is_storage_pattern(line):
    if line.startswith("!"):
        return False
    return (
        line == "storage/"
        or line == "/storage/"
        or line.startswith("storage/")
        or line.startswith("/storage/")
    )


def test_backend_gitignore_lists_env_and_storage():
    path = BACKEND_DIR / ".gitignore"
    if not path.is_file():
        pytest.fail("backend/.gitignore is missing")
    lines = active_gitignore_lines(path.read_text(encoding="utf-8"))
    assert any(is_dotenv_pattern(line) for line in lines), "backend/.gitignore must list .env"
    assert any(is_storage_pattern(line) for line in lines), "backend/.gitignore must list storage/"


def test_git_check_ignore_backend_env():
    env_path = BACKEND_DIR / ".env"
    created = False
    if not env_path.exists():
        env_path.write_text("", encoding="utf-8")
        created = True
    try:
        completed = subprocess.run(
            ["git", "check-ignore", "-q", "backend/.env"],
            cwd=REPO_ROOT,
            check=False,
        )
        assert completed.returncode == 0, "git check-ignore -q backend/.env failed"
    finally:
        if created:
            env_path.unlink(missing_ok=True)


def is_sensitive_name(name):
    upper = name.upper()
    if any(token in upper for token in MARKER_NAMES):
        return True
    return re.search(r"(?<![A-Z0-9])PAT(?![A-Z0-9])", upper) is not None


def strip_inline_comment(value):
    in_single = False
    in_double = False
    for index, char in enumerate(value):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            return value[:index]
    return value


def is_empty_assignment(value):
    cleaned = strip_inline_comment(value).strip().rstrip(";").strip()
    return cleaned in {"", '""', "''", '""""""', "''''''"}


def test_tracked_files_have_no_secret_assignments():
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    hits = []
    for relative in completed.stdout.decode("utf-8").split("\0"):
        if not relative:
            continue
        path = REPO_ROOT / relative
        if not path.is_file():
            pytest.fail(f"tracked file is missing from the worktree: {relative}")
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for match in ASSIGNMENT.finditer(line):
                name = match.group("name")
                if not is_sensitive_name(name):
                    continue
                if is_empty_assignment(match.group("value")):
                    continue
                hits.append(f"{relative}:{line_no}: {name}")
    assert not hits, "tracked files contain non-empty secret assignments:\n" + "\n".join(hits)


def normalize_name(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_name(spec):
    base = spec.split(";", 1)[0].strip()
    base = base.split("@", 1)[0].strip()
    match = REQUIREMENT_NAME.match(base)
    if match is None:
        pytest.fail(f"unparseable requirement: {spec!r}")
    return normalize_name(match.group(0))


def names_from_requirement_list(items):
    names = set()
    if not isinstance(items, list):
        return names
    for item in items:
        if isinstance(item, str):
            names.add(requirement_name(item))
    return names


def poetry_table_names(table, runtime_only):
    names = set()
    if not isinstance(table, dict):
        return names
    for key, value in table.items():
        if key.lower() == "python":
            continue
        if runtime_only and isinstance(value, dict) and value.get("optional") is True:
            continue
        names.add(requirement_name(key))
    return names


def dependency_group_names(items, groups, seen):
    names = set()
    if not isinstance(items, list):
        return names
    for item in items:
        if isinstance(item, str):
            names.add(requirement_name(item))
        elif isinstance(item, dict) and "include-group" in item:
            group_name = item["include-group"]
            if group_name not in seen and isinstance(groups, dict):
                seen.add(group_name)
                names |= dependency_group_names(groups.get(group_name), groups, seen)
    return names


def dev_dependency_names(data):
    names = set()
    project = data.get("project") or {}
    optional = project.get("optional-dependencies") or {}
    if isinstance(optional, dict) and "dev" in optional:
        names |= names_from_requirement_list(optional["dev"])

    groups = data.get("dependency-groups") or {}
    if isinstance(groups, dict) and "dev" in groups:
        names |= dependency_group_names(groups["dev"], groups, {"dev"})

    poetry = (data.get("tool") or {}).get("poetry") or {}
    names |= poetry_table_names(poetry.get("dev-dependencies") or {}, runtime_only=False)
    group = (poetry.get("group") or {}).get("dev") or {}
    names |= poetry_table_names(group.get("dependencies") or {}, runtime_only=False)
    return names


def runtime_dependency_names(data):
    project = data.get("project") or {}
    names = names_from_requirement_list(project.get("dependencies") or [])
    poetry = (data.get("tool") or {}).get("poetry") or {}
    names |= poetry_table_names(poetry.get("dependencies") or {}, runtime_only=True)
    return names


def every_dependency_name(data):
    names = set(runtime_dependency_names(data))
    project = data.get("project") or {}
    optional = project.get("optional-dependencies") or {}
    if isinstance(optional, dict):
        for items in optional.values():
            names |= names_from_requirement_list(items)

    groups = data.get("dependency-groups") or {}
    if isinstance(groups, dict):
        for group_name, items in groups.items():
            names |= dependency_group_names(items, groups, {group_name})

    poetry = (data.get("tool") or {}).get("poetry") or {}
    names |= poetry_table_names(poetry.get("dependencies") or {}, runtime_only=False)
    names |= poetry_table_names(poetry.get("dev-dependencies") or {}, runtime_only=False)
    for group in (poetry.get("group") or {}).values():
        if isinstance(group, dict):
            names |= poetry_table_names(group.get("dependencies") or {}, runtime_only=False)
    extras = poetry.get("extras") or {}
    if isinstance(extras, dict):
        for items in extras.values():
            names |= names_from_requirement_list(items)
    return names


def is_banned_dependency(name):
    if "elevenlabs" in name or "stedi" in name:
        return True
    return name.startswith("snowflake")


def test_pyproject_declares_runtime_and_dev_dependencies():
    path = BACKEND_DIR / "pyproject.toml"
    if not path.is_file():
        pytest.fail("backend/pyproject.toml is missing")
    with path.open("rb") as handle:
        data = tomllib.load(handle)

    runtime = runtime_dependency_names(data)
    missing = sorted(REQUIRED_RUNTIME - runtime)
    assert not missing, f"backend/pyproject.toml is missing runtime dependencies: {missing}"

    dev = dev_dependency_names(data)
    assert "pytest" in dev, "pytest must be in a dev extra or dependency group"

    banned = sorted(name for name in every_dependency_name(data) if is_banned_dependency(name))
    assert not banned, f"backend/pyproject.toml must not require {banned}"


def is_forbidden_module(module_name):
    for forbidden in FORBIDDEN_MODULES:
        if module_name == forbidden or module_name.startswith(forbidden + "."):
            return True
    return False


def imported_module_name(node):
    func = node.func
    is_import = isinstance(func, ast.Name) and func.id == "__import__"
    is_importlib = isinstance(func, ast.Attribute) and func.attr == "import_module"
    if not is_import and not is_importlib:
        return None
    if not node.args:
        return None
    arg = node.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    return None


def forbidden_imports(source, filename):
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        pytest.fail(f"{filename} could not be parsed: {exc}")
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if is_forbidden_module(alias.name):
                    found.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if base and is_forbidden_module(base):
                found.append(base)
            for alias in node.names:
                combined = f"{base}.{alias.name}" if base else alias.name
                if is_forbidden_module(combined):
                    found.append(combined)
        elif isinstance(node, ast.Call):
            target = imported_module_name(node)
            if target and is_forbidden_module(target):
                found.append(target)
    return found


def test_stub_modules_do_not_import_forbidden_clients():
    app_dir = BACKEND_DIR / "app"
    if not app_dir.is_dir():
        pytest.fail("backend/app is missing")
    files = sorted(path for path in app_dir.rglob("*.py") if path.is_file())
    if not files:
        pytest.fail("backend/app has no Python modules")
    violations = []
    for path in files:
        source = path.read_text(encoding="utf-8")
        hits = forbidden_imports(source, str(path))
        if hits:
            relative = path.relative_to(REPO_ROOT)
            violations.append(f"{relative}: {sorted(set(hits))}")
    assert not violations, "forbidden imports:\n" + "\n".join(violations)


def test_web_and_mobile_directories_do_not_exist():
    assert not (REPO_ROOT / "web").is_dir()
    assert not (REPO_ROOT / "mobile").is_dir()
