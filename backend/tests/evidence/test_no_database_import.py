import ast
from pathlib import Path

import pytest

EVIDENCE_DIR = Path(__file__).resolve().parents[2] / "app" / "evidence"
FORBIDDEN_MODULES = ("app.db", "sqlalchemy", "psycopg")


def _forbidden(module):
    if not module:
        return False
    return any(
        module == name or module.startswith(name + ".") for name in FORBIDDEN_MODULES
    )


def _imported_names(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _forbidden(alias.name):
                    found.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "app":
                for alias in node.names:
                    if alias.name == "db" or alias.name.startswith("db."):
                        found.append((node.lineno, f"app.{alias.name}"))
            if _forbidden(module):
                found.append((node.lineno, module))
            for alias in node.names:
                qualified = f"{module}.{alias.name}" if module else alias.name
                if _forbidden(qualified):
                    found.append((node.lineno, qualified))
        elif isinstance(node, ast.Call):
            func = node.func
            is_import = (
                isinstance(func, ast.Name) and func.id == "__import__"
            ) or (
                isinstance(func, ast.Attribute) and func.attr == "import_module"
            )
            if not is_import or not node.args:
                continue
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if _forbidden(arg.value):
                    found.append((node.lineno, arg.value))
    return found


def test_evidence_package_does_not_import_database():
    if not EVIDENCE_DIR.is_dir():
        pytest.fail("backend/app/evidence is missing")
    sources = [
        path
        for path in EVIDENCE_DIR.rglob("*.py")
        if "__pycache__" not in path.parts
    ]
    if not sources:
        pytest.fail("backend/app/evidence is missing")

    offenders = []
    for path in sources:
        for lineno, name in _imported_names(path):
            offenders.append(f"{path.relative_to(EVIDENCE_DIR)}:{lineno} imports {name}")
    assert offenders == []
