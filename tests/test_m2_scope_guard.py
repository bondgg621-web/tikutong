from __future__ import annotations

import ast
from hashlib import sha256
import inspect
import json
from pathlib import Path
import re
import subprocess
import sys

import pytest

from conftest import REPOSITORY_ROOT, SKILL_ROOT
from m2_helpers import (
    FIXED_TIME,
    UTF8_BOM_CRLF_BYTES,
    UUIDSequence,
    bootstrap_m1_workspace,
    copy_m2_fixture,
    copy_m2_fixture_tree,
    expected_canonical_json_bytes,
    expected_content_revision_fingerprint,
    expected_normalize_text,
    expected_option_set_fingerprint,
    expected_text_fingerprint,
    file_hash,
    fixed_now,
    run_subprocess,
    tree_snapshot,
    write_exact_bytes,
    write_utf8_bom_crlf_fixture,
)


SPEC_SHA256 = "a4e6cfcee04a497243da9282931b1baa99ba1589702420af3c5034d88a6a809c"
IMMUTABLE_AUTHORITY_SHA256 = {
    "schemas/candidate.schema.json": "25e4c5f2a0bb691004d6915d867be73756ce8b51231303bab14b380d1717d39d",
    "schemas/decision.schema.json": "721b8e4cc212a3d0c9c76dee4bb9c974d27117063284832d64bdfbe4c641dc79",
    "schemas/manifest.schema.json": "405c50c6ffc34222ed3d944c4a8ca2b1edae7576802bff8c907347c50e0da2c8",
    "schemas/question-bank-interchange.schema.json": "2ff79b971a5fe0dec21c7ea387241d3cdaf48f5876775b0837543e204ca8ac56",
    "schemas/review-item.schema.json": "91c5c86ec377b11b48936437749a7fafd5b902b976dc0ba7cd2432ae8ea4a4fb",
    "schemas/run-state.schema.json": "fad4d3aa4473f8363e2681d3421d2f3e3bb18b65bd2893b24810b2e63fe42ae3",
    "references/question-types.md": "407984e4d6536aff6ea4f47776e429d2ac9f97c9da9924cbd27049cca3e824b1",
    "references/identity-contract.md": "d208f9b91448996131fde4c9b14d4b526dc521cbee369b956eff9f849198cf18",
    "references/state-contract.md": "868b5f4a2f2225b67d3c39f364f22e4830bc43633b20f04b8095bf26e6dbdf2a",
    "scripts/qbcore/validation.py": "2b0b65e1a844aa65e9f272af479db5d44f2c9c5e32abf1450a1487afc6c4b9d3",
}
STATIC_FIXTURE_NAMES = {
    "fenced.md",
    "malformed.md",
    "strict-seven.md",
    "strict-two.txt",
    "unsupported-type.md",
}
STATIC_FIXTURE_SHA256 = {
    "fenced.md": "5862602ff73acaf9aee34d0202540f808240fda4f2a2b636c7b77aefdc438dc3",
    "malformed.md": "9382c396934dfa506136939c0d075a209647d6f266b0df15eced94f0eec8aedf",
    "strict-seven.md": "2d6a76ecdd76df2c78c63769d061a8552e0c54b2c26a23bc428fe8b9987cfecb",
    "strict-two.txt": "1d75273fc53f01af68355cb9d2f05c846ac33f2df64dd4879700642c6845a4d2",
    "unsupported-type.md": "49b9d07155fd0b5336180b7adb43ea7117ae2fb0b017f29a9596d61f20d599fc",
}
STATIC_FIXTURE_BYTE_LENGTHS = {
    "fenced.md": 222,
    "malformed.md": 84,
    "strict-seven.md": 749,
    "strict-two.txt": 173,
    "unsupported-type.md": 87,
}
SYNTHETIC_FIXTURE_PROVENANCE = {
    "fenced.md": "Synthetic Task-1 engineering example for fenced question text.",
    "malformed.md": "Synthetic Task-1 engineering example with a skipped option label.",
    "strict-seven.md": "Synthetic M0 golden chapter-1 source copied byte-for-byte for Task 1.",
    "strict-two.txt": "Synthetic Task-1 strict-syntax variant example.",
    "unsupported-type.md": "Synthetic Task-1 unsupported marker example.",
}
APPROVED_M2_ISSUE_CODES = {
    "QB-IDENTITY-AMBIGUOUS",
    "QB-SECURITY-INSTRUCTION-DATA",
    "QB-SOURCE-READ-FAILED",
    "QB-SOURCE-UNSUPPORTED",
    "QB-STRUCTURE-AMBIGUOUS",
    "QB-TYPE-UNSUPPORTED",
}
PLANNED_M2_SCHEMA_NAMES = {
    "single-choice-parse-issues.schema.json",
    "single-choice-parse-report.schema.json",
    "single-choice-parse-run.schema.json",
}
# Task 2 requires the complete independent parse-contract schema set.
REQUIRED_M2_SCHEMA_NAMES: frozenset[str] = frozenset(PLANNED_M2_SCHEMA_NAMES)
PRE_M2_QBCORE_SHA256 = {
    "__init__.py": "9172b6b1e3fae974d1bc53b3d36f1551fab3cd6749f63a0517ccce7c80bf31bf",
    "capabilities.py": "76df50692e29228aec7c8b40642343ad765498247a98131c76e894520ab9155e",
    "cli.py": "881fb55d940323897a9f402dedca80b3c96e78a3a7a9570e366ce53af1c97c5a",
    "discovery.py": "901eeaba37a8c7f3de2d0fb531e94489390c9adb1173b161cae45d6d44393563",
    "paths.py": "f3ae1803c4f40ab6984a8d77259c1bdd934d428970cc08e8aceb8760fe3fb32f",
    "recovery.py": "91b6cd0aab9eafcaf4f29278a3778e6af48130f35e393bfe9942ace4246c70f6",
    "registry.py": "972f2b168aca180a9674fd81457e7d406255daee1aacf14da3416af0a1556c14",
    "validation.py": "2b0b65e1a844aa65e9f272af479db5d44f2c9c5e32abf1450a1487afc6c4b9d3",
    "workspace.py": "f359321e48544f3f9761ae788f0c2eeb41695955fd2dc8b3c3ff92aa33ca77f4",
    "workspace_contracts.py": "29b535190d280776438b9735a150f9312073ead5fe9abd1bae19507b50d562fe",
}
PLANNED_M2_MODULE_NAMES = {
    "boundary_detector.py",
    "candidate_materializer.py",
    "option_structure_parser.py",
    "parse_contracts.py",
    "parse_service.py",
    "single_choice_parser.py",
    "text_normalization.py",
}
# Task 8 adds the read-only source-resolution and decoding boundary.
REQUIRED_PLANNED_M2_MODULES: frozenset[str] = frozenset(
    {
        "boundary_detector.py",
        "candidate_materializer.py",
        "option_structure_parser.py",
        "parse_contracts.py",
        "parse_service.py",
        "single_choice_parser.py",
        "text_normalization.py",
    }
)
# Later tasks must declare intentional edits to a pre-M2 module here before its frozen hash may change.
MODIFIED_PRE_M2_MODULES: frozenset[str] = frozenset({"cli.py", "workspace.py"})
FORBIDDEN_IMPORT_ROOTS = {
    "PyPDF2",
    "aiohttp",
    "anthropic",
    "bs4",
    "docx",
    "duckdb",
    "easyocr",
    "ensurepip",
    "fitz",
    "ftplib",
    "html",
    "httpx",
    "lxml",
    "multiprocessing",
    "openai",
    "openpyxl",
    "PIL",
    "pip",
    "pkg_resources",
    "pytesseract",
    "pptx",
    "pypdf",
    "requests",
    "smtplib",
    "socket",
    "sqlalchemy",
    "sqlite3",
    "subprocess",
    "tarfile",
    "telnetlib",
    "urllib",
    "webbrowser",
    "zipfile",
}
FORBIDDEN_FUNCTION_NAMES = {
    "associate_answer",
    "create_decision",
    "install_dependency",
    "migrate_candidate",
    "migrate_option",
    "parse_docx",
    "parse_pdf",
    "parse_pptx",
    "parse_xlsx",
    "promote_validated",
    "rescan_candidates",
}
ANSWER_API_ACTIONS = {
    "apply",
    "associate",
    "association",
    "attach",
    "bind",
    "binding",
    "link",
    "map",
    "match",
    "resolve",
}
DECISION_API_ACTIONS = {
    "build",
    "builder",
    "construct",
    "create",
    "factory",
    "make",
    "materialize",
    "new",
    "publish",
    "record",
    "service",
    "write",
}
UNSUPPORTED_FORMAT_TOKENS = {"docx", "html", "ocr", "pdf", "pptx", "xlsx", "zip"}
UNSUPPORTED_ENTRY_ACTIONS = {
    "adapt",
    "adapter",
    "convert",
    "converter",
    "extract",
    "extractor",
    "load",
    "loader",
    "open",
    "parse",
    "parser",
    "read",
    "reader",
    "scan",
    "scanner",
    "unpack",
}
ANSWER_SEMANTIC_FIELDS = {
    "answer",
    "answer_option_id",
    "correct_option_id",
    "resolved_option_id",
    "selected_option_id",
}
OPTION_ANSWER_SEMANTIC_TOKENS = {"answer", "correct", "resolved", "selected"}


def _import_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def _import_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _qualified_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _qualified_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _symbol_aliases(tree: ast.AST) -> dict[str, str]:
    aliases = {
        "__import__": "builtins.__import__",
        "compile": "builtins.compile",
        "eval": "builtins.eval",
        "exec": "builtins.exec",
        "setattr": "builtins.setattr",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    aliases[alias.asname] = alias.name
                else:
                    root = alias.name.split(".", 1)[0]
                    aliases[root] = root
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    assignment_candidates: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        qualified = _qualified_name(value) if value is not None else None
        if qualified is None:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id not in aliases:
                assignment_candidates.setdefault(target.id, set()).add(qualified)
    for _ in range(len(assignment_candidates) + 1):
        additions: dict[str, str] = {}
        for target, candidates in assignment_candidates.items():
            resolved = {_resolve_qualified_name(candidate, aliases) for candidate in candidates}
            if len(resolved) == 1:
                additions[target] = next(iter(resolved))
        if all(aliases.get(name) == value for name, value in additions.items()):
            break
        aliases.update(additions)
    return aliases


def _resolve_qualified_name(name: str, aliases: dict[str, str]) -> str:
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


def _named_string_constants(tree: ast.AST) -> dict[str, str]:
    literal_candidates: dict[str, set[str]] = {}
    reference_candidates: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not (
            (isinstance(value, ast.Constant) and isinstance(value.value, str))
            or isinstance(value, ast.Name)
        ):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                if isinstance(value, ast.Constant):
                    literal_candidates.setdefault(target.id, set()).add(value.value)
                else:
                    reference_candidates.setdefault(target.id, set()).add(value.id)
    resolved: dict[str, str] = {}
    names = set(literal_candidates) | set(reference_candidates)
    for _ in range(len(names) + 1):
        additions: dict[str, str] = {}
        for name in names:
            references = reference_candidates.get(name, set())
            if not references <= set(resolved):
                continue
            values = set(literal_candidates.get(name, set()))
            values.update(resolved[reference] for reference in references)
            if len(values) == 1:
                additions[name] = next(iter(values))
        if all(resolved.get(name) == value for name, value in additions.items()):
            break
        resolved.update(additions)
    return resolved


def _identifier_tokens(name: str) -> set[str]:
    with_acronym_boundaries = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    with_word_boundaries = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", with_acronym_boundaries)
    return {
        token.casefold()
        for token in re.split(r"[^A-Za-z0-9]+", with_word_boundaries)
        if token
    }


def _forbidden_api_reason(name: str) -> str | None:
    tokens = _identifier_tokens(name)
    if "answer" in tokens and tokens & ANSWER_API_ACTIONS:
        return f"answer-api:{name}"
    if (
        "option" in tokens
        and tokens & OPTION_ANSWER_SEMANTIC_TOKENS
        and tokens & ANSWER_API_ACTIONS
    ):
        return f"answer-option-api:{name}"
    if "decision" in tokens and (tokens == {"decision"} or tokens & DECISION_API_ACTIONS):
        return f"decision-api:{name}"
    formats = tokens & UNSUPPORTED_FORMAT_TOKENS
    if formats and tokens & UNSUPPORTED_ENTRY_ACTIONS:
        return f"unsupported-parser-api:{name}"
    return None


def _is_validated_literal(node: ast.AST, constants: dict[str, str] | None = None) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.casefold() == "validated"
    if isinstance(node, ast.Name) and constants and node.id in constants:
        return constants[node.id].casefold() == "validated"
    return False


def _is_status_target(node: ast.AST) -> bool:
    if isinstance(node, ast.Attribute):
        return node.attr.casefold() == "status"
    if isinstance(node, ast.Subscript):
        key = node.slice
        return isinstance(key, ast.Constant) and isinstance(key.value, str) and key.value.casefold() == "status"
    return False


def _assignment_target_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id.casefold()}
    if isinstance(node, ast.Attribute):
        return {node.attr.casefold()}
    if isinstance(node, ast.Subscript):
        key = node.slice
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            return {key.value.casefold()}
        return set()
    if isinstance(node, (ast.List, ast.Tuple)):
        return set().union(*(_assignment_target_names(item) for item in node.elts))
    return set()


def _dict_sets_validated_status(node: ast.Dict, constants: dict[str, str]) -> bool:
    return any(
        isinstance(key, ast.Constant)
        and isinstance(key.value, str)
        and key.value.casefold() == "status"
        and _is_validated_literal(value, constants)
        for key, value in zip(node.keys, node.values)
        if key is not None
    )


def _dict_has_key(node: ast.Dict, expected: str) -> bool:
    return any(
        isinstance(key, ast.Constant)
        and isinstance(key.value, str)
        and key.value.casefold() == expected.casefold()
        for key in node.keys
        if key is not None
    )


def _executable_scope_violations(source: str, *, filename: str = "<mutation>") -> list[str]:
    tree = ast.parse(source, filename=filename)
    forbidden_roots = {name.casefold() for name in FORBIDDEN_IMPORT_ROOTS}
    aliases = _symbol_aliases(tree)
    string_constants = _named_string_constants(tree)
    found = {
        f"forbidden-import:{root}"
        for root in _import_roots(tree)
        if root.casefold() in forbidden_roots
    }
    for module in _import_modules(tree):
        reason = _forbidden_api_reason(module)
        if reason:
            found.add(reason)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name in FORBIDDEN_FUNCTION_NAMES:
                found.add(f"forbidden-api:{node.name}")
            reason = _forbidden_api_reason(node.name)
            if reason:
                found.add(reason)
        elif isinstance(node, ast.Call):
            syntactic_name = _qualified_name(node.func)
            if syntactic_name is None:
                continue
            qualified = _resolve_qualified_name(syntactic_name, aliases)
            terminal = qualified.rsplit(".", 1)[-1]
            if qualified in {"builtins.eval", "builtins.exec", "builtins.compile"}:
                found.add(f"source-execution:{qualified}")
            if qualified in {"builtins.__import__", "importlib.import_module"}:
                found.add(f"dynamic-import:{qualified}")
            if qualified in {"os.popen", "os.system"} or qualified.startswith("os.spawn"):
                found.add(f"process-launch:{qualified}")
            reason = _forbidden_api_reason(terminal)
            if reason:
                found.add(reason)
            if qualified == "builtins.setattr" and len(node.args) >= 3:
                if (
                    isinstance(node.args[1], ast.Constant)
                    and isinstance(node.args[1].value, str)
                    and node.args[1].value.casefold() == "status"
                    and _is_validated_literal(node.args[2], string_constants)
                ):
                    found.add("validated-status:setattr")
                if (
                    isinstance(node.args[1], ast.Constant)
                    and isinstance(node.args[1].value, str)
                    and node.args[1].value.casefold() in ANSWER_SEMANTIC_FIELDS
                ):
                    found.add(f"answer-semantics:setattr:{node.args[1].value}")
            if any(keyword.arg == "status" and _is_validated_literal(keyword.value, string_constants) for keyword in node.keywords):
                found.add(f"validated-status:{qualified}")
            if any(keyword.arg == "decision_id" for keyword in node.keywords):
                found.add(f"decision-construction:{qualified}")
            semantic_keywords = {
                keyword.arg.casefold()
                for keyword in node.keywords
                if keyword.arg is not None and keyword.arg.casefold() in ANSWER_SEMANTIC_FIELDS
            }
            for field in semantic_keywords:
                found.add(f"answer-semantics:{qualified}:{field}")
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if value is not None and _is_validated_literal(value, string_constants) and any(_is_status_target(target) for target in targets):
                found.add("validated-status:assignment")
            semantic_targets = set().union(*(_assignment_target_names(target) for target in targets)) & ANSWER_SEMANTIC_FIELDS
            for field in semantic_targets:
                found.add(f"answer-semantics:assignment:{field}")
        elif isinstance(node, ast.NamedExpr):
            semantic_targets = _assignment_target_names(node.target) & ANSWER_SEMANTIC_FIELDS
            for field in semantic_targets:
                found.add(f"answer-semantics:named-expression:{field}")
        elif isinstance(node, ast.Dict):
            if _dict_sets_validated_status(node, string_constants):
                found.add("validated-status:document")
            if _dict_has_key(node, "decision_id"):
                found.add("decision-construction:document")
            for field in ANSWER_SEMANTIC_FIELDS:
                if _dict_has_key(node, field):
                    found.add(f"answer-semantics:document:{field}")
    return sorted(found)


def _scan_qbcore_package(
    root: Path,
    *,
    pre_m2_hashes: dict[str, str],
    planned_names: set[str],
    required_planned: set[str] | frozenset[str] = frozenset(),
    modified_pre_m2: set[str] | frozenset[str] = frozenset(),
) -> dict[str, list[str]]:
    if not set(required_planned) <= planned_names:
        raise ValueError("required planned modules must be declared in planned_names")
    if not set(modified_pre_m2) <= set(pre_m2_hashes):
        raise ValueError("modified pre-M2 modules must exist in the frozen manifest")

    actual = {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*.py")
        if path.is_file()
    }
    allowed = set(pre_m2_hashes) | planned_names
    violations: dict[str, list[str]] = {}

    def add(name: str, reason: str) -> None:
        violations.setdefault(name, []).append(reason)

    for name in sorted(set(actual) - allowed):
        add(name, "manifest:unexpected-module")
    for name in sorted(set(pre_m2_hashes) - set(actual)):
        add(name, "manifest:pre-m2-module-missing")
    for name in sorted(set(required_planned) - set(actual)):
        add(name, "manifest:required-module-missing")

    for name in sorted(set(actual) & set(pre_m2_hashes)):
        if name not in modified_pre_m2 and file_hash(actual[name]) != pre_m2_hashes[name]:
            add(name, "manifest:pre-m2-hash-changed")

    for name in sorted(set(actual) & allowed):
        try:
            reasons = _executable_scope_violations(
                actual[name].read_text(encoding="utf-8"),
                filename=str(actual[name]),
            )
        except (SyntaxError, UnicodeDecodeError):
            add(name, "manifest:module-not-utf8-python")
            continue
        for reason in reasons:
            add(name, reason)
    return {
        name: sorted(set(reasons))
        for name, reasons in sorted(violations.items())
    }


def _scan_m2_schemas(
    root: Path,
    *,
    planned_names: set[str],
    required_names: set[str] | frozenset[str],
    approved_codes: set[str],
) -> dict[str, list[str]]:
    if not set(required_names) <= planned_names:
        raise ValueError("required schemas must be declared in planned_names")
    actual = {
        path.name: path
        for path in root.glob("*.schema.json")
        if path.is_file()
        and (path.name in planned_names or path.name.startswith("single-choice-"))
    }
    violations: dict[str, list[str]] = {}

    def add(name: str, reason: str) -> None:
        violations.setdefault(name, []).append(reason)

    for name in sorted(set(actual) - planned_names):
        add(name, "schema-manifest:unexpected-schema")
    for name in sorted(set(required_names) - set(actual)):
        add(name, "schema-manifest:required-schema-missing")

    present_planned = set(actual) & planned_names
    if present_planned and present_planned != planned_names:
        for name in sorted(planned_names - present_planned):
            add(name, "schema-manifest:incomplete-planned-set")
    elif present_planned == planned_names:
        for name in sorted(planned_names):
            try:
                document = json.loads(actual[name].read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                add(name, "schema-manifest:not-utf8-json")
                continue
            codes = set(re.findall(r"QB-[A-Za-z0-9_-]+", json.dumps(document, ensure_ascii=False)))
            for code in sorted(codes - approved_codes):
                add(name, f"issue-code:not-approved:{code}")
    return {
        name: sorted(set(reasons))
        for name, reasons in sorted(violations.items())
    }


def test_frozen_spec_and_m0_authorities_have_expected_byte_hashes() -> None:
    spec = REPOSITORY_ROOT / "docs" / "MILESTONE-2-SINGLE-CHOICE-PARSER-SPEC.md"
    assert file_hash(spec) == SPEC_SHA256
    assert {
        relative: file_hash(SKILL_ROOT / relative)
        for relative in IMMUTABLE_AUTHORITY_SHA256
    } == IMMUTABLE_AUTHORITY_SHA256


def test_static_m2_fixtures_are_complete_and_synthetic() -> None:
    fixture_root = REPOSITORY_ROOT / "tests" / "fixtures" / "m2-parser"
    assert {path.name for path in fixture_root.iterdir() if path.is_file()} == STATIC_FIXTURE_NAMES
    assert (fixture_root / "strict-seven.md").read_bytes() == (
        REPOSITORY_ROOT / "tests" / "fixtures" / "golden-course" / "course" / "chapter-1-questions.md"
    ).read_bytes()
    for name in sorted(STATIC_FIXTURE_NAMES):
        path = fixture_root / name
        payload = path.read_text(encoding="utf-8")
        assert "synthetic" in payload.casefold() or name == "strict-seven.md"


def test_static_fixture_manifest_pins_each_declared_file_independently() -> None:
    fixture_root = REPOSITORY_ROOT / "tests" / "fixtures" / "m2-parser"
    assert set(STATIC_FIXTURE_SHA256) == STATIC_FIXTURE_NAMES
    assert set(STATIC_FIXTURE_BYTE_LENGTHS) == STATIC_FIXTURE_NAMES
    assert set(SYNTHETIC_FIXTURE_PROVENANCE) == STATIC_FIXTURE_NAMES
    assert {
        name: file_hash(fixture_root / name)
        for name in sorted(STATIC_FIXTURE_NAMES)
    } == STATIC_FIXTURE_SHA256
    assert {
        name: (fixture_root / name).stat().st_size
        for name in sorted(STATIC_FIXTURE_NAMES)
    } == STATIC_FIXTURE_BYTE_LENGTHS
    assert all("synthetic" in description.casefold() for description in SYNTHETIC_FIXTURE_PROVENANCE.values())


def test_deterministic_helpers_copy_and_hash_exact_bytes(tmp_path: Path) -> None:
    sequence = UUIDSequence(10)
    assert fixed_now() == FIXED_TIME
    assert [str(sequence()), str(sequence())] == [
        "00000000-0000-4000-8000-00000000000a",
        "00000000-0000-4000-8000-00000000000b",
    ]

    exact = write_exact_bytes(tmp_path / "exact" / "bytes.bin", b"a\x00b\n")
    bom = write_utf8_bom_crlf_fixture(tmp_path / "utf8-bom-crlf.txt")
    copied = copy_m2_fixture("strict-two.txt", tmp_path / "copied" / "strict-two.txt")
    copied_tree = copy_m2_fixture_tree(tmp_path / "fixture-tree")
    assert exact.read_bytes() == b"a\x00b\n"
    assert bom.read_bytes() == UTF8_BOM_CRLF_BYTES
    assert b"\n" not in bom.read_bytes().removeprefix(b"\xef\xbb\xbf").replace(b"\r\n", b"")
    assert file_hash(copied) == file_hash(copied_tree / "strict-two.txt")
    assert tree_snapshot(copied_tree) == tree_snapshot(
        REPOSITORY_ROOT / "tests" / "fixtures" / "m2-parser"
    )


def test_expected_fingerprint_helpers_are_independent_oracles() -> None:
    decomposed = "  Cafe\u0301\t synthetic\ntext  "
    assert expected_normalize_text(decomposed) == "Café synthetic text"
    assert expected_canonical_json_bytes({"stem": "Café", "options": ["A", "B"]}) == (
        b'{"options":["A","B"],"stem":"Caf\xc3\xa9"}'
    )
    assert expected_text_fingerprint(decomposed) == sha256("Café synthetic text".encode()).hexdigest()
    assert expected_option_set_fingerprint([" B ", "A", "A"]) == sha256(b'["A","A","B"]').hexdigest()
    expected_payload = b'{"options":["A","B"],"question_type":"single_choice","stem":"Synthetic"}'
    assert expected_content_revision_fingerprint(" Synthetic ", ["A", "B"]) == sha256(expected_payload).hexdigest()


def test_workspace_bootstrap_uses_real_m1_inventory(tmp_path: Path) -> None:
    bootstrapped = bootstrap_m1_workspace(
        tmp_path,
        fixture_names=("strict-two.txt",),
        uuid_start=20,
    )
    assert bootstrapped.result.status == "complete"
    assert bootstrapped.discovery["entries"] == [{
        "relative_path": "strict-two.txt",
        "size_bytes": (bootstrapped.input_root / "strict-two.txt").stat().st_size,
        "content_hash": file_hash(bootstrapped.input_root / "strict-two.txt"),
        "support_status": "builtin_text",
    }]
    assert bootstrapped.registry["sources"][0]["current_relative_path"] == "strict-two.txt"


def test_subprocess_helper_forces_no_bytecode(tmp_path: Path) -> None:
    completed = run_subprocess(
        (sys.executable, "-c", "import os; print(os.environ['PYTHONDONTWRITEBYTECODE'])"),
        cwd=tmp_path,
        env={"PYTHONDONTWRITEBYTECODE": "overridden"},
    )
    assert completed.returncode == 0
    assert completed.stdout.strip() == "1"


def test_subprocess_helper_forces_utf8_unicode_round_trip(tmp_path: Path) -> None:
    completed = run_subprocess(
        (
            sys.executable,
            "-c",
            "import os; print('合成✓'); print(os.environ['PYTHONUTF8']); print(os.environ['PYTHONIOENCODING'])",
        ),
        cwd=tmp_path,
        env={"PYTHONUTF8": "0", "PYTHONIOENCODING": "ascii"},
    )
    assert completed.returncode == 0
    assert completed.stdout.splitlines() == ["合成✓", "1", "utf-8"]


def test_subprocess_helper_has_bounded_default_timeout() -> None:
    timeout = inspect.signature(run_subprocess).parameters["timeout"].default
    assert isinstance(timeout, float | int)
    assert 0 < timeout <= 60


def test_subprocess_helper_raises_timeout_expired(tmp_path: Path) -> None:
    with pytest.raises(subprocess.TimeoutExpired):
        run_subprocess(
            (sys.executable, "-c", "import time; time.sleep(2)"),
            cwd=tmp_path,
            timeout=0.05,
        )


def test_future_m2_schemas_use_only_approved_issue_codes() -> None:
    schema_root = SKILL_ROOT / "schemas"
    present = {name for name in PLANNED_M2_SCHEMA_NAMES if (schema_root / name).is_file()}
    assert present == set(REQUIRED_M2_SCHEMA_NAMES)
    assert _scan_m2_schemas(
        schema_root,
        planned_names=PLANNED_M2_SCHEMA_NAMES,
        required_names=REQUIRED_M2_SCHEMA_NAMES,
        approved_codes=APPROVED_M2_ISSUE_CODES,
    ) == {}


def test_m2_schema_scanner_allows_explicit_task1_absence(tmp_path: Path) -> None:
    assert _scan_m2_schemas(
        tmp_path,
        planned_names={"report.schema.json", "issues.schema.json", "run.schema.json"},
        required_names=set(),
        approved_codes=APPROVED_M2_ISSUE_CODES,
    ) == {}


def test_m2_schema_scanner_rejects_partial_planned_set(tmp_path: Path) -> None:
    write_exact_bytes(tmp_path / "report.schema.json", b"{}")
    assert _scan_m2_schemas(
        tmp_path,
        planned_names={"report.schema.json", "issues.schema.json", "run.schema.json"},
        required_names=set(),
        approved_codes=APPROVED_M2_ISSUE_CODES,
    ) == {
        "issues.schema.json": ["schema-manifest:incomplete-planned-set"],
        "run.schema.json": ["schema-manifest:incomplete-planned-set"],
    }


def test_m2_schema_scanner_requires_current_stage_names(tmp_path: Path) -> None:
    assert _scan_m2_schemas(
        tmp_path,
        planned_names={"report.schema.json", "issues.schema.json", "run.schema.json"},
        required_names={"report.schema.json"},
        approved_codes=APPROVED_M2_ISSUE_CODES,
    ) == {"report.schema.json": ["schema-manifest:required-schema-missing"]}


def test_m2_schema_scanner_checks_codes_after_complete_set(tmp_path: Path) -> None:
    for name in ("report.schema.json", "issues.schema.json", "run.schema.json"):
        code = "QB-NOT-APPROVED" if name == "issues.schema.json" else "QB-SOURCE-UNSUPPORTED"
        write_exact_bytes(tmp_path / name, json.dumps({"enum": [code]}).encode("utf-8"))
    assert _scan_m2_schemas(
        tmp_path,
        planned_names={"report.schema.json", "issues.schema.json", "run.schema.json"},
        required_names=set(),
        approved_codes=APPROVED_M2_ISSUE_CODES,
    ) == {"issues.schema.json": ["issue-code:not-approved:QB-NOT-APPROVED"]}


@pytest.mark.parametrize(
    "code",
    (
        "QB-SOURCE-UNSUPPORTED2",
        "QB-SOURCE-UNSUPPORTED-extra",
        "QB-SOURCE-UNSUPPORTED_EXTRA",
    ),
    ids=("numeric-suffix", "lowercase-suffix", "underscore-suffix"),
)
def test_m2_schema_scanner_rejects_full_unapproved_issue_token(tmp_path: Path, code: str) -> None:
    for name in ("report.schema.json", "issues.schema.json", "run.schema.json"):
        value = code if name == "issues.schema.json" else "QB-SOURCE-UNSUPPORTED"
        write_exact_bytes(tmp_path / name, json.dumps({"enum": [value]}).encode("utf-8"))
    assert _scan_m2_schemas(
        tmp_path,
        planned_names={"report.schema.json", "issues.schema.json", "run.schema.json"},
        required_names=set(),
        approved_codes=APPROVED_M2_ISSUE_CODES,
    ) == {"issues.schema.json": [f"issue-code:not-approved:{code}"]}


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "from builtins import eval as evaluate\nevaluate(source_text)\n",
            "source-execution:builtins.eval",
        ),
        (
            "import os as platform_os\nplatform_os.system(command)\n",
            "process-launch:os.system",
        ),
        (
            "from os import system\nsystem(command)\n",
            "process-launch:os.system",
        ),
        (
            "import importlib\nload_module = importlib.import_module\nload_module('requests')\n",
            "dynamic-import:importlib.import_module",
        ),
        (
            "VALIDATED = 'validated'\ncandidate['status'] = VALIDATED\n",
            "validated-status:assignment",
        ),
    ],
    ids=("eval-alias", "os-module-alias", "os-call-alias", "assigned-importer", "validated-constant"),
)
def test_scope_guard_resolves_forbidden_symbols(source: str, expected: str) -> None:
    assert _executable_scope_violations(source) == [expected]


def test_scope_guard_binds_root_for_unaliased_dotted_import() -> None:
    source = "import os.path\nos.system(command)\n"
    assert _executable_scope_violations(source) == ["process-launch:os.system"]


def test_scope_guard_resolves_chained_validated_string_constants() -> None:
    source = "VALIDATED = 'validated'\nSTATUS = VALIDATED\ncandidate.status = STATUS\n"
    assert _executable_scope_violations(source) == ["validated-status:assignment"]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("eval(source_text)\n", "source-execution:builtins.eval"),
        ("exec(source_text)\n", "source-execution:builtins.exec"),
        ("compile(source_text, '<source>', 'exec')\n", "source-execution:builtins.compile"),
        ("import importlib\nimportlib.import_module('requests')\n", "dynamic-import:importlib.import_module"),
        ("__import__('subprocess')\n", "dynamic-import:builtins.__import__"),
        ("candidate['status'] = 'validated'\n", "validated-status:assignment"),
        ("candidate.status = 'validated'\n", "validated-status:assignment"),
        ("candidate = {'status': 'validated'}\n", "validated-status:document"),
        ("def link_answer_to_option(candidate, answer):\n    return candidate\n", "answer-api:link_answer_to_option"),
        ("class AnswerBindingService:\n    pass\n", "answer-api:AnswerBindingService"),
        ("def bind_correct_option(candidate, answer):\n    return candidate\n", "answer-option-api:bind_correct_option"),
        ("def associate_correct_option(candidate, option):\n    return candidate\n", "answer-option-api:associate_correct_option"),
        ("Decision(candidate_id, option_id)\n", "decision-api:Decision"),
        ("contracts.Decision(candidate_id, option_id)\n", "decision-api:Decision"),
        ("DecisionRecord(candidate_id='synthetic')\n", "decision-api:DecisionRecord"),
        ("class DecisionBuilder:\n    pass\n", "decision-api:DecisionBuilder"),
        ("decision = {'decision_id': 'synthetic'}\n", "decision-construction:document"),
        ("dict(decision_id='synthetic')\n", "decision-construction:dict"),
        ("answer = source_text\n", "answer-semantics:assignment:answer"),
        ("resolved_option_id = option_id\n", "answer-semantics:assignment:resolved_option_id"),
        ("candidate['answer'] = source_text\n", "answer-semantics:assignment:answer"),
        ("candidate.resolved_option_id = option_id\n", "answer-semantics:assignment:resolved_option_id"),
        ("candidate['answer_option_id'] = option_id\n", "answer-semantics:assignment:answer_option_id"),
        ("candidate['correct_option_id'] = option_id\n", "answer-semantics:assignment:correct_option_id"),
        ("candidate = {'answer': source_text}\n", "answer-semantics:document:answer"),
        ("candidate.update(resolved_option_id=option_id)\n", "answer-semantics:candidate.update:resolved_option_id"),
        ("answer: str = source_text\n", "answer-semantics:assignment:answer"),
        ("if (answer := source_text):\n    pass\n", "answer-semantics:named-expression:answer"),
        ("answer, remainder = values\n", "answer-semantics:assignment:answer"),
        ("setattr(candidate, 'answer', source_text)\n", "answer-semantics:setattr:answer"),
        ("def read_html_document(source):\n    return source\n", "unsupported-parser-api:read_html_document"),
        ("class OcrAdapter:\n    pass\n", "unsupported-parser-api:OcrAdapter"),
        ("def unpack_zip_source(source):\n    return source\n", "unsupported-parser-api:unpack_zip_source"),
        ("def load_pdf(source):\n    return source\n", "unsupported-parser-api:load_pdf"),
        ("def parse_docx_source(source):\n    return source\n", "unsupported-parser-api:parse_docx_source"),
        ("def read_xlsx(source):\n    return source\n", "unsupported-parser-api:read_xlsx"),
        ("class PptxParser:\n    pass\n", "unsupported-parser-api:PptxParser"),
    ],
    ids=(
        "eval", "exec", "compile", "dynamic-import", "dunder-import",
        "validated-subscript", "validated-attribute", "validated-document",
        "answer-link", "answer-binding", "correct-option-binding", "correct-option-association",
        "decision", "qualified-decision", "decision-record", "decision-builder", "decision-document",
        "decision-keyword", "local-answer", "local-resolved-option", "subscript-answer",
        "attribute-resolved-option", "answer-option", "correct-option", "answer-document",
        "resolved-option-update", "annotated-answer", "walrus-answer", "unpacked-answer",
        "setattr-answer", "html", "ocr", "zip", "pdf", "docx", "xlsx", "pptx",
    ),
)
def test_scope_guard_reports_exact_mutation_reason(source: str, expected: str) -> None:
    assert _executable_scope_violations(source) == [expected]


def test_scope_guard_allows_normal_parser_vocabulary() -> None:
    source = '''
ANSWER_PREFIX = "Answer:"

def classify_plain_text(line: str) -> str:
    """Treat answer, decision, HTML, OCR, and ZIP words as inert source text."""
    return "validated" if line == "literal vocabulary only" else line

def classify_answer_like_text(answer_like_text: str) -> tuple[str, str]:
    resolved_option_id_like_text = "resolved_option_id"
    return answer_like_text, resolved_option_id_like_text
'''
    assert _executable_scope_violations(source) == []


def test_qbcore_scanner_rejects_unexpected_python_module(tmp_path: Path) -> None:
    root = tmp_path / "qbcore"
    root.mkdir()
    existing = write_exact_bytes(root / "existing.py", b"VALUE = 1\n")
    write_exact_bytes(root / "unexpected.py", b"VALUE = 2\n")
    assert _scan_qbcore_package(
        root,
        pre_m2_hashes={"existing.py": file_hash(existing)},
        planned_names={"future.py"},
    ) == {"unexpected.py": ["manifest:unexpected-module"]}


def test_qbcore_scanner_allows_absent_optional_planned_module(tmp_path: Path) -> None:
    root = tmp_path / "qbcore"
    root.mkdir()
    existing = write_exact_bytes(root / "existing.py", b"VALUE = 1\n")
    assert _scan_qbcore_package(
        root,
        pre_m2_hashes={"existing.py": file_hash(existing)},
        planned_names={"future.py"},
    ) == {}


def test_qbcore_scanner_requires_declared_stage_module(tmp_path: Path) -> None:
    root = tmp_path / "qbcore"
    root.mkdir()
    existing = write_exact_bytes(root / "existing.py", b"VALUE = 1\n")
    assert _scan_qbcore_package(
        root,
        pre_m2_hashes={"existing.py": file_hash(existing)},
        planned_names={"future.py"},
        required_planned={"future.py"},
    ) == {"future.py": ["manifest:required-module-missing"]}


def test_qbcore_scanner_requires_frozen_pre_m2_module(tmp_path: Path) -> None:
    root = tmp_path / "qbcore"
    root.mkdir()
    assert _scan_qbcore_package(
        root,
        pre_m2_hashes={"existing.py": sha256(b"VALUE = 1\n").hexdigest()},
        planned_names=set(),
    ) == {"existing.py": ["manifest:pre-m2-module-missing"]}


def test_qbcore_scanner_scans_planned_module_as_soon_as_it_exists(tmp_path: Path) -> None:
    root = tmp_path / "qbcore"
    root.mkdir()
    existing = write_exact_bytes(root / "existing.py", b"VALUE = 1\n")
    write_exact_bytes(root / "future.py", b"eval(source_text)\n")
    assert _scan_qbcore_package(
        root,
        pre_m2_hashes={"existing.py": file_hash(existing)},
        planned_names={"future.py"},
    ) == {"future.py": ["source-execution:builtins.eval"]}


def test_qbcore_scanner_rejects_undeclared_pre_m2_hash_change(tmp_path: Path) -> None:
    root = tmp_path / "qbcore"
    root.mkdir()
    write_exact_bytes(root / "existing.py", b"CHANGED = True\n")
    assert _scan_qbcore_package(
        root,
        pre_m2_hashes={"existing.py": sha256(b"VALUE = 1\n").hexdigest()},
        planned_names=set(),
    ) == {"existing.py": ["manifest:pre-m2-hash-changed"]}


def test_qbcore_scanner_scans_declared_pre_m2_stage_change(tmp_path: Path) -> None:
    root = tmp_path / "qbcore"
    root.mkdir()
    write_exact_bytes(root / "existing.py", b"eval(source_text)\n")
    assert _scan_qbcore_package(
        root,
        pre_m2_hashes={"existing.py": sha256(b"VALUE = 1\n").hexdigest()},
        planned_names=set(),
        modified_pre_m2={"existing.py"},
    ) == {"existing.py": ["source-execution:builtins.eval"]}


def test_executable_m2_scope_has_no_forbidden_capabilities() -> None:
    qbcore_root = SKILL_ROOT / "scripts" / "qbcore"
    assert _scan_qbcore_package(
        qbcore_root,
        pre_m2_hashes=PRE_M2_QBCORE_SHA256,
        planned_names=PLANNED_M2_MODULE_NAMES,
        required_planned=REQUIRED_PLANNED_M2_MODULES,
        modified_pre_m2=MODIFIED_PRE_M2_MODULES,
    ) == {}
