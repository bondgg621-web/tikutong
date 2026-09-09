from __future__ import annotations

from copy import deepcopy
import importlib
import json
from pathlib import Path

import jsonschema
import pytest

from conftest import SKILL_ROOT


KINDS = {
    "single-choice-parse-report",
    "single-choice-parse-issues",
    "single-choice-parse-run",
}
U1 = "00000000-0000-4000-8000-000000000001"
U2 = "00000000-0000-4000-8000-000000000002"
U3 = "00000000-0000-4000-8000-000000000003"
H1 = "a" * 64
H2 = "b" * 64
H3 = "c" * 64
STAMP = "2026-08-14T00:00:00Z"

ISSUE_RULES = {
    "QB-SOURCE-UNSUPPORTED": ("blocking", ["retain", "exclude", "provide adapter"]),
    "QB-SOURCE-READ-FAILED": ("blocking", ["retry", "retain", "exclude"]),
    "QB-TYPE-UNSUPPORTED": ("blocking", ["retain", "mark unsupported"]),
    "QB-STRUCTURE-AMBIGUOUS": (
        "review_required",
        ["correct source", "retain", "exclude"],
    ),
    "QB-IDENTITY-AMBIGUOUS": (
        "blocking",
        ["confirm mapping", "archive decision"],
    ),
    "QB-SECURITY-INSTRUCTION-DATA": (
        "blocking",
        ["retain as data", "quarantine"],
    ),
}


def schema_path(kind: str) -> Path:
    return SKILL_ROOT / "schemas" / f"{kind}.schema.json"


def load_schema(kind: str) -> dict:
    return json.loads(schema_path(kind).read_text(encoding="utf-8"))


def contracts_module():
    return importlib.import_module("qbcore.parse_contracts")


def runtime_errors(kind: str, value: object) -> list:
    return contracts_module().validate_parse_document(kind, value)


def schema_errors(kind: str, value: object) -> list:
    return list(jsonschema.Draft202012Validator(load_schema(kind)).iter_errors(value))


def schema_error_paths(kind: str, value: object) -> set[str]:
    paths: set[str] = set()

    def collect(error) -> None:
        paths.add(".".join(str(part) for part in error.absolute_path))
        for child in error.context:
            collect(child)

    for error in schema_errors(kind, value):
        collect(error)
    return paths


def report_document(*, status: str = "complete") -> dict:
    complete = status == "complete"
    review = status == "needs_review"
    return {
        "schema_version": "1.0",
        "parser_contract_version": "m2-single-choice-v1",
        "run_id": U1,
        "status": status,
        "source_id": U2,
        "source_revision": 1,
        "source_relative_path": "chapter-1/questions.md",
        "source_content_hash": H1,
        "question_like_block_count": 1,
        "accepted_candidate_count": 1 if complete else 0,
        "rejected_block_count": 0,
        "finding_count": 1 if review else 0,
        "candidate_artifact_relative_path": (
            f"candidates/sources/{U2}.json" if complete else None
        ),
        "candidate_artifact_content_hash": H2 if complete else None,
    }


def issue_value(code: str = "QB-SOURCE-UNSUPPORTED") -> dict:
    level, actions = ISSUE_RULES[code]
    return {
        "issue_id": U3,
        "code": code,
        "blocking_level": level,
        "status": "open",
        "source_id": U2,
        "locator": "line:1",
        "summary": "Unsupported source adapter at line:1.",
        "allowed_user_actions": actions,
    }


def issues_document(*, with_issue: bool = False) -> dict:
    return {
        "schema_version": "1.0",
        "run_id": U1,
        "source_id": U2,
        "issues": [issue_value()] if with_issue else [],
    }


def run_document(*, status: str = "complete") -> dict:
    artifacts = [
        {
            "kind": "parse_report",
            "relative_path": f"runs/{U1}/parse-report.json",
            "content_hash": H1,
        },
        {
            "kind": "parse_issues",
            "relative_path": f"runs/{U1}/parse-issues.json",
            "content_hash": H2,
        },
    ]
    if status == "complete":
        artifacts.append(
            {
                "kind": "candidate",
                "relative_path": f"candidates/sources/{U2}.json",
                "content_hash": H2,
            }
        )
    return {
        "schema_version": "1.0",
        "run_id": U1,
        "source_id": U2,
        "phase": "complete" if status in {"complete", "needs_review"} else "parse",
        "status": status,
        "started_at": STAMP,
        "updated_at": STAMP,
        "input_root_fingerprint": H1,
        "workspace_root_fingerprint": H2,
        "artifacts": artifacts if status in {"complete", "needs_review"} else [],
    }


def all_object_schemas(value: object):
    if isinstance(value, dict):
        if value.get("type") == "object":
            yield value
        for child in value.values():
            yield from all_object_schemas(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_object_schemas(child)


def test_parse_contract_registry_and_schema_paths_are_explicit() -> None:
    module = contracts_module()
    assert module.PARSE_DOCUMENT_KINDS == frozenset(KINDS)
    for kind in KINDS:
        assert module.parse_schema_path(kind) == schema_path(kind)
    with pytest.raises(ValueError, match="unknown parse document kind"):
        module.parse_schema_path("workspace-run")


def test_every_parse_schema_is_valid_closed_draft_2020_12_without_source_body_fields() -> None:
    forbidden = {"source_text", "source_body", "raw_text", "excerpt", "stem", "option_text"}
    for kind in KINDS:
        schema = load_schema(kind)
        jsonschema.Draft202012Validator.check_schema(schema)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        objects = list(all_object_schemas(schema))
        assert objects
        assert all(node.get("additionalProperties") is False for node in objects)
        property_names = {
            name
            for node in objects
            for name in node.get("properties", {})
        }
        assert property_names.isdisjoint(forbidden)


def test_valid_minimal_documents_pass_runtime_and_jsonschema() -> None:
    values = {
        "single-choice-parse-report": report_document(),
        "single-choice-parse-issues": issues_document(),
        "single-choice-parse-run": run_document(),
    }
    for kind, value in values.items():
        assert runtime_errors(kind, value) == []
        assert schema_errors(kind, value) == []


def test_integral_float_is_a_json_schema_integer_in_runtime_and_jsonschema() -> None:
    value = report_document()
    value["source_revision"] = 1.0
    assert schema_errors("single-choice-parse-report", value) == []
    assert runtime_errors("single-choice-parse-report", value) == []


def test_report_semantics_accept_integral_float_counts() -> None:
    value = report_document()
    value["question_like_block_count"] = 1.0
    value["accepted_candidate_count"] = 1.0
    value["rejected_block_count"] = 0.0
    value["finding_count"] = 0.0
    assert schema_errors("single-choice-parse-report", value) == []
    assert runtime_errors("single-choice-parse-report", value) == []


@pytest.mark.parametrize("value", [1.5, True])
def test_fractional_float_and_bool_are_not_json_schema_integers(value: object) -> None:
    document = report_document()
    document["source_revision"] = value
    assert schema_errors("single-choice-parse-report", document)
    assert runtime_errors("single-choice-parse-report", document)


@pytest.mark.parametrize("code", sorted(ISSUE_RULES))
def test_every_frozen_issue_mapping_passes_runtime_and_jsonschema(code: str) -> None:
    value = issues_document()
    value["issues"] = [issue_value(code)]
    assert runtime_errors("single-choice-parse-issues", value) == []
    assert schema_errors("single-choice-parse-issues", value) == []


MALFORMED_ISSUE_FIELD_VALUES = {
    "code": [None, True, 1, "QB-NOT-APPROVED", [], {}],
    "status": [None, True, 1, "resolved", [], {}],
    "blocking_level": [None, True, 1, "informational", [], {}],
    "allowed_user_actions": [None, True, 1, "retain", [], {}],
}


@pytest.mark.parametrize(
    ("field", "malformed"),
    [
        (field, malformed)
        for field, values in MALFORMED_ISSUE_FIELD_VALUES.items()
        for malformed in values
    ],
)
def test_malformed_issue_fields_never_crash_and_report_the_field(
    field: str,
    malformed: object,
) -> None:
    value = issues_document(with_issue=True)
    value["issues"][0][field] = malformed

    runtime = runtime_errors("single-choice-parse-issues", value)
    assert runtime
    assert all(isinstance(issue, contracts_module().ParseContractIssue) for issue in runtime)
    assert any(issue.path.endswith(f".{field}") for issue in runtime)

    development = schema_errors("single-choice-parse-issues", value)
    assert development
    assert any(
        path.endswith(f"issues.0.{field}")
        for path in schema_error_paths("single-choice-parse-issues", value)
    )


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_missing_required_and_additional_fields_fail_runtime_and_jsonschema(kind: str) -> None:
    original = {
        "single-choice-parse-report": report_document(),
        "single-choice-parse-issues": issues_document(),
        "single-choice-parse-run": run_document(),
    }[kind]
    missing = deepcopy(original)
    missing.pop("schema_version")
    additional = deepcopy(original)
    additional["source_text"] = "must never enter an artifact"
    for invalid in (missing, additional):
        assert runtime_errors(kind, invalid)
        assert schema_errors(kind, invalid)


def schema_negative_vectors() -> list[tuple[str, dict]]:
    vectors: list[tuple[str, dict]] = []

    invalid = report_document()
    invalid["run_id"] = "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"
    vectors.append(("single-choice-parse-report", invalid))
    invalid = report_document()
    invalid["source_content_hash"] = "A" * 64
    vectors.append(("single-choice-parse-report", invalid))
    invalid = report_document()
    invalid["source_revision"] = 0
    vectors.append(("single-choice-parse-report", invalid))
    invalid = report_document()
    invalid["accepted_candidate_count"] = True
    vectors.append(("single-choice-parse-report", invalid))
    invalid = report_document()
    invalid["status"] = "partial"
    vectors.append(("single-choice-parse-report", invalid))
    invalid = report_document()
    invalid["parser_contract_version"] = "m2-single-choice-v2"
    vectors.append(("single-choice-parse-report", invalid))
    invalid = report_document()
    invalid["source_relative_path"] = ""
    vectors.append(("single-choice-parse-report", invalid))

    invalid = issues_document(with_issue=True)
    invalid["issues"][0]["locator"] = "question-1"
    vectors.append(("single-choice-parse-issues", invalid))
    invalid = issues_document(with_issue=True)
    invalid["issues"][0]["issue_id"] = "not-a-uuid"
    vectors.append(("single-choice-parse-issues", invalid))
    invalid = issues_document(with_issue=True)
    invalid["issues"][0]["code"] = "QB-ANSWER-MISSING"
    vectors.append(("single-choice-parse-issues", invalid))
    invalid = issues_document(with_issue=True)
    invalid["issues"][0]["status"] = "resolved"
    vectors.append(("single-choice-parse-issues", invalid))

    invalid = run_document()
    invalid["started_at"] = "2026-08-14T08:00:00+08:00"
    vectors.append(("single-choice-parse-run", invalid))
    invalid = run_document()
    invalid["input_root_fingerprint"] = "a" * 63
    vectors.append(("single-choice-parse-run", invalid))
    invalid = run_document()
    invalid["phase"] = "candidate"
    vectors.append(("single-choice-parse-run", invalid))
    invalid = run_document()
    invalid["status"] = "cancelled"
    vectors.append(("single-choice-parse-run", invalid))
    invalid = run_document()
    invalid["artifacts"][0]["kind"] = "registry"
    vectors.append(("single-choice-parse-run", invalid))
    return vectors


@pytest.mark.parametrize(("kind", "invalid"), schema_negative_vectors())
def test_schema_level_negative_vectors_fail_runtime_and_jsonschema(kind: str, invalid: dict) -> None:
    assert runtime_errors(kind, invalid)
    assert schema_errors(kind, invalid)


def patterned_terminal_vectors() -> list[tuple[str, dict, str]]:
    vectors: list[tuple[str, dict, str]] = []
    cases = (
        ("single-choice-parse-report", report_document, "run_id", U1),
        ("single-choice-parse-report", report_document, "source_content_hash", H1),
        ("single-choice-parse-run", run_document, "started_at", STAMP),
    )
    for kind, factory, field, original in cases:
        for suffix in ("\n", "\r\n", "trailing-junk"):
            value = factory()
            value[field] = original + suffix
            vectors.append((kind, value, field))
    for suffix in ("\n", "\r\n", "trailing-junk"):
        value = issues_document(with_issue=True)
        value["issues"][0]["locator"] = "line:1" + suffix
        vectors.append(("single-choice-parse-issues", value, "issues.0.locator"))
    return vectors


@pytest.mark.parametrize(("kind", "invalid", "field_path"), patterned_terminal_vectors())
def test_patterned_strings_reject_terminal_newlines_crlf_and_junk_with_parity(
    kind: str,
    invalid: dict,
    field_path: str,
) -> None:
    runtime = runtime_errors(kind, invalid)
    development = schema_errors(kind, invalid)
    assert runtime
    assert development
    assert any(issue.path.replace("[", ".").replace("]", "").endswith(field_path) for issue in runtime)
    assert any(path.endswith(field_path) for path in schema_error_paths(kind, invalid))


@pytest.mark.parametrize("field", ["blocking_level", "allowed_user_actions"])
def test_issue_code_level_and_action_order_are_frozen_in_schema_and_runtime(field: str) -> None:
    invalid = issues_document(with_issue=True)
    if field == "blocking_level":
        invalid["issues"][0][field] = "review_required"
    else:
        invalid["issues"][0][field] = list(reversed(invalid["issues"][0][field]))
    runtime = runtime_errors("single-choice-parse-issues", invalid)
    field_errors = [error for error in runtime if error.path.endswith(f".{field}")]
    assert len(field_errors) == 1
    assert schema_errors("single-choice-parse-issues", invalid)


@pytest.mark.parametrize(
    ("path_value", "hash_value"),
    ((None, H2), (f"candidates/sources/{U2}.json", None)),
)
def test_report_candidate_path_and_hash_must_be_a_null_pair(
    path_value: str | None,
    hash_value: str | None,
) -> None:
    invalid = report_document(status="failed")
    invalid["candidate_artifact_relative_path"] = path_value
    invalid["candidate_artifact_content_hash"] = hash_value
    assert runtime_errors("single-choice-parse-report", invalid)


@pytest.mark.parametrize(
    ("status", "updates"),
    (
        ("complete", {"accepted_candidate_count": 0}),
        ("complete", {"finding_count": 1}),
        ("complete", {"rejected_block_count": 1}),
        (
            "complete",
            {
                "candidate_artifact_relative_path": None,
                "candidate_artifact_content_hash": None,
            },
        ),
        (
            "needs_review",
            {
                "candidate_artifact_relative_path": f"candidates/sources/{U2}.json",
                "candidate_artifact_content_hash": H2,
            },
        ),
        ("needs_review", {"finding_count": 0}),
        (
            "failed",
            {
                "candidate_artifact_relative_path": f"candidates/sources/{U2}.json",
                "candidate_artifact_content_hash": H2,
            },
        ),
    ),
)
def test_report_status_counts_and_candidate_artifact_are_consistent(
    status: str,
    updates: dict,
) -> None:
    invalid = report_document(status=status)
    invalid.update(updates)
    assert runtime_errors("single-choice-parse-report", invalid)


def test_report_candidate_path_is_the_frozen_source_target() -> None:
    invalid = report_document()
    invalid["candidate_artifact_relative_path"] = "candidates/other.json"
    assert runtime_errors("single-choice-parse-report", invalid)


def test_review_and_failed_reports_are_valid_without_candidate_artifacts() -> None:
    for status in ("needs_review", "failed"):
        value = report_document(status=status)
        assert runtime_errors("single-choice-parse-report", value) == []
        assert schema_errors("single-choice-parse-report", value) == []


def test_issue_document_source_matches_every_issue() -> None:
    invalid = issues_document(with_issue=True)
    invalid["issues"][0]["source_id"] = U3
    assert runtime_errors("single-choice-parse-issues", invalid)


@pytest.mark.parametrize(
    "unsafe",
    (
        "/absolute/report.json",
        "C:/absolute/report.json",
        "../report.json",
        "runs/../report.json",
        "runs/report.json:alternate-stream",
    ),
)
def test_run_artifact_paths_are_safe_relative_paths(unsafe: str) -> None:
    invalid = run_document()
    invalid["artifacts"][0]["relative_path"] = unsafe
    assert runtime_errors("single-choice-parse-run", invalid)


WINDOWS_RESERVED_PATHS = tuple(
    f"safe/{name}{extension}"
    for name in (
        "CON",
        "prn",
        "AuX",
        "nul",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"lpt{index}" for index in range(1, 10)),
    )
    for extension in ("", ".json")
)
UNSAFE_LEXICAL_PATHS = (
    "/absolute.json",
    "C:/absolute.json",
    "../escape.json",
    "safe/../escape.json",
    "./relative.json",
    "safe//empty.json",
    "safe\\backslash.json",
    "safe/stream.json:ads",
    "safe/trailing./file.json",
    "safe/trailing /file.json",
    "safe/file.json.",
    "safe/file.json ",
    "safe/control\x01.json",
    "safe/control\x7f.json",
    "safe/control\x85.json",
) + WINDOWS_RESERVED_PATHS

EXTENDED_WINDOWS_RESERVED_PATHS = (
    "safe/CONIN$",
    "safe/conin$.json",
    "safe/ConOut$",
    "safe/CONOUT$.TXT",
    "safe/COM¹",
    "safe/com¹.json",
    "safe/Com².TXT",
    "safe/cOM³.data",
    "safe/LPT¹",
    "safe/lpt¹.json",
    "safe/LpT².TXT",
    "safe/lPT³.data",
)
INVALID_WINDOWS_FILENAME_PATHS = (
    "safe/bad<name.json",
    "safe/bad>name.json",
    "safe/bad:name.json",
    'safe/bad"name.json',
    "safe/bad|name.json",
    "safe/bad?name.json",
    "safe/bad*name.json",
    "safe/bad\\name.json",
    "/safe/name.json",
    "safe//name.json",
    "safe/name.json/",
)


@pytest.mark.parametrize("unsafe", UNSAFE_LEXICAL_PATHS)
def test_source_and_artifact_paths_share_strict_windows_lexical_safety(unsafe: str) -> None:
    report = report_document()
    report["source_relative_path"] = unsafe
    report_errors = runtime_errors("single-choice-parse-report", report)
    assert any(
        error.path.endswith(".source_relative_path") and "safe relative path" in error.message
        for error in report_errors
    )

    run = run_document()
    run["artifacts"][0]["relative_path"] = unsafe
    run_errors = runtime_errors("single-choice-parse-run", run)
    assert any(
        error.path.endswith(".relative_path") and "safe relative path" in error.message
        for error in run_errors
    )


@pytest.mark.parametrize(
    "unsafe",
    EXTENDED_WINDOWS_RESERVED_PATHS + INVALID_WINDOWS_FILENAME_PATHS,
)
def test_extended_windows_devices_and_filename_characters_are_unsafe(unsafe: str) -> None:
    report = report_document()
    report["source_relative_path"] = unsafe
    errors = runtime_errors("single-choice-parse-report", report)
    assert any(error.path.endswith(".source_relative_path") for error in errors)


@pytest.mark.parametrize(
    ("status", "phase", "kinds"),
    (
        ("complete", "publication", ["parse_report", "parse_issues", "candidate"]),
        ("complete", "complete", ["parse_report", "parse_issues"]),
        ("needs_review", "parse", ["parse_report", "parse_issues"]),
        ("needs_review", "complete", ["parse_report", "parse_issues", "candidate"]),
        ("failed", "parse", ["parse_report", "parse_report"]),
        ("running", "parse", ["parse_issues", "parse_issues"]),
    ),
)
def test_run_status_phase_artifact_sets_and_uniqueness_are_consistent(
    status: str,
    phase: str,
    kinds: list[str],
) -> None:
    invalid = run_document(status=status)
    invalid["phase"] = phase
    invalid["artifacts"] = [
        {
            "kind": kind,
            "relative_path": f"artifacts/{index}.json",
            "content_hash": H1,
        }
        for index, kind in enumerate(kinds)
    ]
    assert runtime_errors("single-choice-parse-run", invalid)


def test_run_artifact_relative_paths_are_unique_independently_of_kind() -> None:
    invalid = run_document()
    invalid["artifacts"][1]["relative_path"] = invalid["artifacts"][0]["relative_path"]
    errors = runtime_errors("single-choice-parse-run", invalid)
    assert any("relative paths must be unique" in error.message for error in errors)


@pytest.mark.parametrize(
    ("kind", "wrong_path"),
    (
        ("parse_report", f"runs/{U1}/other-report.json"),
        ("parse_issues", f"runs/{U1}/other-issues.json"),
        ("candidate", "candidates/sources/other.json"),
    ),
)
def test_run_artifact_kind_requires_its_canonical_path(kind: str, wrong_path: str) -> None:
    invalid = run_document()
    artifact = next(item for item in invalid["artifacts"] if item["kind"] == kind)
    artifact["relative_path"] = wrong_path
    errors = runtime_errors("single-choice-parse-run", invalid)
    assert any(error.path.endswith(".relative_path") for error in errors)


def test_failed_and_running_runs_allow_unique_artifact_subsets() -> None:
    for status in ("failed", "running"):
        value = run_document(status=status)
        value["artifacts"] = [
                {
                    "kind": "parse_report",
                    "relative_path": f"runs/{U1}/parse-report.json",
                    "content_hash": H1,
                }
        ]
        assert runtime_errors("single-choice-parse-run", value) == []


def test_needs_review_run_allows_exact_report_and_issues_artifacts() -> None:
    value = run_document(status="needs_review")
    assert runtime_errors("single-choice-parse-run", value) == []
    assert schema_errors("single-choice-parse-run", value) == []


@pytest.mark.parametrize(
    ("document_name", "field", "replacement"),
    (
        ("report", "run_id", U3),
        ("issues", "run_id", U3),
        ("run", "source_id", U3),
        ("issues", "source_id", U3),
        ("run", "status", "needs_review"),
    ),
)
def test_cross_document_validator_rejects_identity_and_status_mismatches(
    document_name: str,
    field: str,
    replacement: str,
) -> None:
    documents = {
        "report": report_document(),
        "issues": issues_document(),
        "run": run_document(),
    }
    documents[document_name][field] = replacement
    if document_name == "run" and field == "status":
        documents["run"]["artifacts"] = documents["run"]["artifacts"][:2]
    assert contracts_module().validate_parse_contracts(
        documents["report"], documents["issues"], documents["run"]
    )


def test_cross_document_validator_compares_declared_hashes_without_filesystem_io() -> None:
    run = run_document()
    declared = {artifact["relative_path"]: artifact["content_hash"] for artifact in run["artifacts"]}
    assert contracts_module().validate_parse_contracts(
        report_document(), issues_document(), run, artifact_content_hashes=declared
    ) == []
    declared[run["artifacts"][0]["relative_path"]] = H3
    assert contracts_module().validate_parse_contracts(
        report_document(), issues_document(), run, artifact_content_hashes=declared
    )


def issue_document_with_count(count: int) -> dict:
    value = issues_document()
    value["issues"] = []
    for index in range(count):
        issue = issue_value()
        issue["issue_id"] = f"00000000-0000-4000-8000-{index + 3:012d}"
        value["issues"].append(issue)
    return value


@pytest.mark.parametrize(
    ("status", "finding_count", "issue_count", "valid"),
    (
        ("complete", 0, 0, True),
        ("complete", 0, 1, False),
        ("needs_review", 1, 1, True),
        ("needs_review", 2, 2, True),
        ("needs_review", 1, 2, False),
        ("failed", 0, 0, True),
        ("failed", 2, 2, True),
        ("failed", 0, 1, False),
    ),
)
def test_cross_document_finding_count_matches_issue_cardinality(
    status: str,
    finding_count: int,
    issue_count: int,
    valid: bool,
) -> None:
    report = report_document(status=status)
    report["finding_count"] = finding_count
    issues = issue_document_with_count(issue_count)
    run = run_document(status=status)
    errors = contracts_module().validate_parse_contracts(report, issues, run)
    if valid:
        assert errors == []
    else:
        assert any(error.path == "cross_document.parse_issues.issues" for error in errors)


@pytest.mark.parametrize("field", ["relative_path", "content_hash"])
def test_cross_document_validator_compares_candidate_declarations(field: str) -> None:
    report = report_document()
    run = run_document()
    candidate = next(artifact for artifact in run["artifacts"] if artifact["kind"] == "candidate")
    candidate["relative_path"] = report["candidate_artifact_relative_path"]
    candidate["content_hash"] = report["candidate_artifact_content_hash"]
    assert contracts_module().validate_parse_contracts(report, issues_document(), run) == []
    candidate[field] = "other/candidate.json" if field == "relative_path" else H3
    assert contracts_module().validate_parse_contracts(report, issues_document(), run)


def test_runtime_issues_are_deterministic_structured_values() -> None:
    invalid = report_document()
    invalid.pop("schema_version")
    invalid["unexpected"] = True
    first = runtime_errors("single-choice-parse-report", invalid)
    second = runtime_errors("single-choice-parse-report", invalid)
    assert first == second
    assert first
    assert all(issue.code and issue.path and issue.message for issue in first)


def test_runtime_has_no_jsonschema_dependency() -> None:
    source = (
        SKILL_ROOT / "scripts" / "qbcore" / "parse_contracts.py"
    ).read_text(encoding="utf-8")
    assert "import jsonschema" not in source
    assert "from jsonschema" not in source
