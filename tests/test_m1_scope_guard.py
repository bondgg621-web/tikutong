import ast
from pathlib import Path

from conftest import SKILL_ROOT


FORBIDDEN_RUNTIME_NAMES = {
    "parser.py",
    "answer_association.py",
    "candidate_builder.py",
    "incremental_executor.py",
}
FROZEN_M0 = {
    "candidate.schema.json",
    "decision.schema.json",
    "manifest.schema.json",
    "question-bank-interchange.schema.json",
    "review-item.schema.json",
    "run-state.schema.json",
}


def test_m1_does_not_add_forbidden_runtime_modules() -> None:
    runtime = SKILL_ROOT / "scripts" / "qbcore"
    assert not ({path.name for path in runtime.glob("*.py")} & FORBIDDEN_RUNTIME_NAMES)


def test_m0_schema_set_remains_present_and_distinct_from_m1() -> None:
    schemas = {path.name for path in (SKILL_ROOT / "schemas").glob("*.json")}
    assert FROZEN_M0 <= schemas
    assert "workspace-run.schema.json" not in FROZEN_M0


FORBIDDEN_CALL_NAMES = {"parse_question", "associate_answer", "build_candidate", "skip_unchanged"}


def test_m1_runtime_does_not_define_forbidden_pipeline_functions() -> None:
    runtime = SKILL_ROOT / "scripts" / "qbcore"
    found: set[str] = set()
    for path in runtime.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        found.update(node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
    assert not (found & FORBIDDEN_CALL_NAMES)


def test_m0_validator_remains_contract_only() -> None:
    text = (SKILL_ROOT / "scripts" / "qbcore" / "validation.py").read_text(encoding="utf-8")
    assert "scan directories" in text
    assert "parse source files" in text
    assert "associate cross-file content" in text
