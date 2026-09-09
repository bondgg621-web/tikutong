from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "skills" / "curate-question-bank" / "scripts" / "qbassist"
EXPECTED_MODULES = frozenset({"__init__.py", "extracted_question.py", "compiler.py"})
FORBIDDEN_IMPORT_ROOTS = {
    "aiohttp",
    "anthropic",
    "bs4",
    "docx",
    "duckdb",
    "ensurepip",
    "fitz",
    "ftplib",
    "http",
    "httpx",
    "importlib",
    "multiprocessing",
    "openai",
    "os",
    "pathlib",
    "PIL",
    "pip",
    "pymongo",
    "pypdf",
    "requests",
    "smtplib",
    "socket",
    "sqlalchemy",
    "sqlite3",
    "subprocess",
    "urllib",
    "venv",
    "webbrowser",
}
ALLOWED_PROJECT_IMPORTS = {
    "qbbank.question_bank",
    "qbbank.validation",
    "qbproduction.question_item",
}


def _manifest_violations(root: Path) -> list[str]:
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*.py")
        if path.is_file()
    }
    return [
        *(f"missing-module:{name}" for name in sorted(EXPECTED_MODULES - actual)),
        *(f"unexpected-module:{name}" for name in sorted(actual - EXPECTED_MODULES)),
    ]


def _qualified_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _qualified_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _capability_violations(source: str, *, filename: str = "<source>") -> list[str]:
    tree = ast.parse(source, filename=filename)
    violations: set[str] = set()
    for node in ast.walk(tree):
        modules: list[str] = []
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
        for module in modules:
            root = module.split(".", 1)[0]
            if root in FORBIDDEN_IMPORT_ROOTS:
                violations.add(f"forbidden-import:{module}")
            if root in {"qbcore", "qbanswer"}:
                violations.add(f"forbidden-project-import:{module}")
            if root in {"qbbank", "qbproduction"} and module not in ALLOWED_PROJECT_IMPORTS:
                violations.add(f"forbidden-project-import:{module}")
        if isinstance(node, ast.Call):
            name = _qualified_name(node.func)
            if name in {"__import__", "compile", "eval", "exec", "importlib.import_module"}:
                violations.add(f"dynamic-execution:{name}")
    return sorted(violations)


def test_scope_guard_detects_future_modules_and_forbidden_capabilities(tmp_path: Path) -> None:
    package = tmp_path / "qbassist"
    package.mkdir()
    for name in EXPECTED_MODULES - {"compiler.py"}:
        (package / name).write_text("", encoding="utf-8")
    (package / "reader.py").write_text("", encoding="utf-8")

    assert _manifest_violations(package) == [
        "missing-module:compiler.py",
        "unexpected-module:reader.py",
    ]
    for source, expected in (
        ("import socket", "forbidden-import:socket"),
        ("import subprocess", "forbidden-import:subprocess"),
        ("import pathlib", "forbidden-import:pathlib"),
        ("import pypdf", "forbidden-import:pypdf"),
        ("import qbcore", "forbidden-project-import:qbcore"),
        ("eval('1')", "dynamic-execution:eval"),
        ("exec('x=1')", "dynamic-execution:exec"),
        ("compile('1', 'x', 'eval')", "dynamic-execution:compile"),
    ):
        assert expected in _capability_violations(source)


def test_qbassist_manifest_and_capabilities_are_exact() -> None:
    assert _manifest_violations(PACKAGE_ROOT) == []
    violations = {
        path.relative_to(PACKAGE_ROOT).as_posix(): findings
        for path in sorted(PACKAGE_ROOT.rglob("*.py"))
        if (findings := _capability_violations(
            path.read_text(encoding="utf-8"), filename=str(path)
        ))
    }
    assert violations == {}
