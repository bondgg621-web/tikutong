from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION_ROOT = ROOT / "skills" / "curate-question-bank" / "scripts" / "qbproduction"
EXPECTED_MODULES = frozenset(
    {
        "__init__.py",
        "batch_assembly.py",
        "cli.py",
        "csv_exporter.py",
        "csv_projection.py",
        "export_projection.py",
        "__main__.py",
        "pipeline.py",
        "question_item.py",
        "question_item_materializer.py",
    }
)
ALLOWED_QBCORE_MODULES = {
    "qbcore.candidate_materializer",
    "qbcore.single_choice_parser",
    "qbcore.validation",
}
FORBIDDEN_IMPORT_ROOTS = {
    "aiohttp",
    "anthropic",
    "duckdb",
    "ensurepip",
    "ftplib",
    "http",
    "httpx",
    "multiprocessing",
    "openai",
    "pip",
    "pkg_resources",
    "pymongo",
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


def _qualified_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _qualified_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _aliases(tree: ast.AST) -> dict[str, str]:
    aliases = {
        "__import__": "builtins.__import__",
        "compile": "builtins.compile",
        "eval": "builtins.eval",
        "exec": "builtins.exec",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".", 1)[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"

    assignments = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)]
    for _ in range(len(assignments) + 1):
        changed = False
        for node in assignments:
            name = _qualified_name(node.value)
            if name is None:
                continue
            resolved = _resolve(name, aliases)
            for target in node.targets:
                if isinstance(target, ast.Name) and aliases.get(target.id) != resolved:
                    aliases[target.id] = resolved
                    changed = True
        if not changed:
            break
    return aliases


def _resolve(name: str, aliases: dict[str, str]) -> str:
    parts = name.split(".")
    seen: set[str] = set()
    while parts[0] in aliases and parts[0] not in seen:
        head = parts[0]
        seen.add(head)
        replacement = aliases[head].split(".")
        if replacement == [head]:
            break
        parts = replacement + parts[1:]
    return ".".join(parts)


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


def _capability_violations(source: str, *, filename: str = "<source>") -> list[str]:
    tree = ast.parse(source, filename=filename)
    aliases = _aliases(tree)
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
            if root == "qbanswer":
                violations.add(f"forbidden-internal-import:{module}")
            if root == "qbcore" and module not in ALLOWED_QBCORE_MODULES:
                violations.add(f"forbidden-internal-import:{module}")

        if not isinstance(node, ast.Call):
            continue
        name = _qualified_name(node.func)
        if name is None:
            continue
        qualified = _resolve(name, aliases)
        if qualified in {
            "builtins.__import__",
            "builtins.compile",
            "builtins.eval",
            "builtins.exec",
            "importlib.import_module",
        }:
            violations.add(f"dynamic-execution:{qualified}")
        if qualified in {"os.popen", "os.system"} or qualified.startswith("os.spawn"):
            violations.add(f"process-launch:{qualified}")
    return sorted(violations)


def test_manifest_guard_detects_missing_and_unexpected_modules(tmp_path: Path) -> None:
    root = tmp_path / "qbproduction"
    root.mkdir()
    for name in EXPECTED_MODULES - {"export_projection.py"}:
        (root / name).write_text("", encoding="utf-8")
    (root / "surprise.py").write_text("", encoding="utf-8")

    assert _manifest_violations(root) == [
        "missing-module:export_projection.py",
        "unexpected-module:surprise.py",
    ]


def test_capability_guard_detects_forbidden_examples() -> None:
    examples = {
        "import socket\nsocket.create_connection(('example.invalid', 443))\n": "forbidden-import:socket",
        "import sqlite3\nsqlite3.connect('state.db')\n": "forbidden-import:sqlite3",
        "import subprocess\nsubprocess.run(['tool'])\n": "forbidden-import:subprocess",
        "import importlib\nload = importlib.import_module\nload('requests')\n": "dynamic-execution:importlib.import_module",
        "import os as platform_os\nplatform_os.system('tool')\n": "process-launch:os.system",
        "from qbanswer.service import prepare\n": "forbidden-internal-import:qbanswer.service",
        "from qbcore.parse_service import run_single_choice_parse\n": "forbidden-internal-import:qbcore.parse_service",
    }
    for source, expected in examples.items():
        assert expected in _capability_violations(source)


def test_qbproduction_scope_and_capabilities_are_exact() -> None:
    assert _manifest_violations(EXTENSION_ROOT) == []
    violations = {
        path.relative_to(EXTENSION_ROOT).as_posix(): findings
        for path in sorted(EXTENSION_ROOT.rglob("*.py"))
        if (findings := _capability_violations(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        ))
    }
    assert violations == {}
