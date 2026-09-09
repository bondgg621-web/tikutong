from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
import math
from pathlib import Path, PureWindowsPath
import re
from typing import Any
import unicodedata


PARSE_DOCUMENT_KINDS = frozenset(
    {
        "single-choice-parse-report",
        "single-choice-parse-issues",
        "single-choice-parse-run",
    }
)
_SCHEMA_FILES = {kind: f"{kind}.schema.json" for kind in PARSE_DOCUMENT_KINDS}
_COMPLETE_ARTIFACT_KINDS = {"parse_report", "parse_issues", "candidate"}
_REVIEW_ARTIFACT_KINDS = {"parse_report", "parse_issues"}
_DRIVE_PATH = re.compile(r"^[A-Za-z]:")
_INVALID_WINDOWS_SEGMENT_CHARACTERS = frozenset('<>"|?*')


@dataclass(frozen=True)
class ParseContractIssue:
    code: str
    path: str
    message: str


def parse_schema_path(kind: str) -> Path:
    try:
        filename = _SCHEMA_FILES[kind]
    except KeyError as error:
        raise ValueError(f"unknown parse document kind: {kind}") from error
    return Path(__file__).resolve().parents[2] / "schemas" / filename


def _issue(issues: list[ParseContractIssue], path: str, message: str) -> None:
    issues.append(ParseContractIssue("QB-PARSE-CONTRACT", path, message))


def _is_json_schema_integer(value: Any) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
    ) or (
        isinstance(value, float)
        and math.isfinite(value)
        and value.is_integer()
    )


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return _is_json_schema_integer(value)
    if expected == "null":
        return value is None
    raise ValueError(f"unsupported parse schema type: {expected}")


def _validate_node(
    value: Any,
    schema: dict,
    path: str,
    issues: list[ParseContractIssue],
) -> None:
    if "oneOf" in schema:
        choices = schema["oneOf"]
        if isinstance(value, dict) and all(
            isinstance(choice.get("properties", {}).get("code", {}).get("const"), str)
            for choice in choices
        ):
            discriminator = value.get("code")
            if not isinstance(discriminator, str):
                _issue(issues, f"{path}.code", "must have type string")
                return
            selected = [
                choice
                for choice in choices
                if choice["properties"]["code"]["const"] == discriminator
            ]
            if len(selected) != 1:
                _issue(issues, f"{path}.code", "must be one of the frozen issue codes")
                return
            _validate_node(value, selected[0], path, issues)
            return

        matches = 0
        for choice in choices:
            choice_issues: list[ParseContractIssue] = []
            _validate_node(value, choice, path, choice_issues)
            if not choice_issues:
                matches += 1
        if matches != 1:
            _issue(issues, path, "must match exactly one frozen schema variant")
        return

    expected = schema.get("type")
    if expected is not None:
        choices = expected if isinstance(expected, list) else [expected]
        if not any(_matches_type(value, choice) for choice in choices):
            _issue(issues, path, f"must have type {' or '.join(choices)}")
            return
    if "const" in schema and value != schema["const"]:
        _issue(issues, path, f"must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        _issue(issues, path, "must be one of the frozen enum values")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            _issue(issues, path, "must not be empty")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            _issue(issues, path, "does not match the required pattern")
    if _is_json_schema_integer(value):
        if value < schema.get("minimum", value):
            _issue(issues, path, f"must be at least {schema['minimum']}")
    if isinstance(value, dict):
        required = set(schema.get("required", []))
        for key in sorted(required - set(value)):
            _issue(issues, f"{path}.{key}", "is required")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in sorted(set(value) - set(properties)):
                _issue(issues, f"{path}.{key}", "is not allowed")
        for key, child_schema in properties.items():
            if key in value:
                _validate_node(value[key], child_schema, f"{path}.{key}", issues)
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            _validate_node(item, schema["items"], f"{path}[{index}]", issues)


def _is_safe_relative_path(value: str) -> bool:
    if not value or "\\" in value or ":" in value:
        return False
    if value.startswith("/") or _DRIVE_PATH.match(value):
        return False
    if any(unicodedata.category(character) == "Cc" for character in value):
        return False
    for part in value.split("/"):
        if part in {"", ".", ".."} or part.endswith((".", " ")):
            return False
        if any(character in _INVALID_WINDOWS_SEGMENT_CHARACTERS for character in part):
            return False
        if PureWindowsPath(part).is_reserved():
            return False
    return True


def _validate_report(value: dict, issues: list[ParseContractIssue]) -> None:
    root = "single-choice-parse-report"
    candidate_path = value.get("candidate_artifact_relative_path")
    candidate_hash = value.get("candidate_artifact_content_hash")
    source_path = value.get("source_relative_path")
    if isinstance(source_path, str) and not _is_safe_relative_path(source_path):
        _issue(
            issues,
            f"{root}.source_relative_path",
            "must be a safe relative path under Windows lexical rules",
        )
    if (candidate_path is None) != (candidate_hash is None):
        _issue(issues, root, "candidate artifact path and hash must both be null or non-null")

    source_id = value.get("source_id")
    if isinstance(candidate_path, str) and isinstance(source_id, str):
        expected = f"candidates/sources/{source_id}.json"
        if candidate_path != expected:
            _issue(
                issues,
                f"{root}.candidate_artifact_relative_path",
                "must use the frozen per-source candidate path",
            )

    status = value.get("status")
    accepted = value.get("accepted_candidate_count")
    findings = value.get("finding_count")
    rejected = value.get("rejected_block_count")
    if status == "complete":
        if not _is_json_schema_integer(accepted) or accepted <= 0:
            _issue(issues, f"{root}.accepted_candidate_count", "complete requires a positive count")
        if findings != 0:
            _issue(issues, f"{root}.finding_count", "complete requires zero findings")
        if rejected != 0:
            _issue(issues, f"{root}.rejected_block_count", "complete requires zero rejected blocks")
        if candidate_path is None:
            _issue(issues, f"{root}.candidate_artifact_relative_path", "complete requires a candidate artifact")
    elif status == "needs_review":
        if candidate_path is not None:
            _issue(issues, f"{root}.candidate_artifact_relative_path", "needs_review forbids a candidate artifact")
        if not _is_json_schema_integer(findings) or findings <= 0:
            _issue(issues, f"{root}.finding_count", "needs_review requires at least one finding")
    elif status == "failed" and candidate_path is not None:
        _issue(issues, f"{root}.candidate_artifact_relative_path", "failed forbids a candidate artifact")


def _validate_issues(value: dict, issues: list[ParseContractIssue]) -> None:
    root = "single-choice-parse-issues"
    document_source_id = value.get("source_id")
    entries = value.get("issues")
    if not isinstance(entries, list):
        return
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        path = f"{root}.issues[{index}]"
        if entry.get("source_id") != document_source_id:
            _issue(issues, f"{path}.source_id", "must match the document source_id")


def _validate_run(value: dict, issues: list[ParseContractIssue]) -> None:
    root = "single-choice-parse-run"
    status = value.get("status")
    phase = value.get("phase")
    if status in {"complete", "needs_review"} and phase != "complete":
        _issue(issues, f"{root}.phase", f"{status} requires the complete phase")

    artifacts = value.get("artifacts")
    if not isinstance(artifacts, list):
        return
    kinds: list[str] = []
    relative_paths: list[str] = []
    run_id = value.get("run_id")
    source_id = value.get("source_id")
    canonical_paths = {
        "parse_report": f"runs/{run_id}/parse-report.json",
        "parse_issues": f"runs/{run_id}/parse-issues.json",
        "candidate": f"candidates/sources/{source_id}.json",
    }
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            continue
        kind = artifact.get("kind")
        if isinstance(kind, str):
            kinds.append(kind)
        relative_path = artifact.get("relative_path")
        if isinstance(relative_path, str):
            relative_paths.append(relative_path)
            if not _is_safe_relative_path(relative_path):
                _issue(
                    issues,
                    f"{root}.artifacts[{index}].relative_path",
                    "must be a safe relative path without traversal",
                )
            if isinstance(kind, str) and relative_path != canonical_paths.get(kind):
                _issue(
                    issues,
                    f"{root}.artifacts[{index}].relative_path",
                    "must use the canonical path for its artifact kind",
                )
    if len(kinds) != len(set(kinds)):
        _issue(issues, f"{root}.artifacts", "artifact kinds must be unique")
    if len(relative_paths) != len(set(relative_paths)):
        _issue(issues, f"{root}.artifacts", "artifact relative paths must be unique")
    kind_set = set(kinds)
    if status == "complete" and kind_set != _COMPLETE_ARTIFACT_KINDS:
        _issue(issues, f"{root}.artifacts", "complete requires exactly report, issues, and candidate artifacts")
    if status == "needs_review" and kind_set != _REVIEW_ARTIFACT_KINDS:
        _issue(issues, f"{root}.artifacts", "needs_review requires exactly report and issues artifacts")


def validate_parse_document(kind: str, value: Any) -> list[ParseContractIssue]:
    if kind not in PARSE_DOCUMENT_KINDS:
        raise ValueError(f"unknown parse document kind: {kind}")
    schema = json.loads(parse_schema_path(kind).read_text(encoding="utf-8"))
    issues: list[ParseContractIssue] = []
    _validate_node(value, schema, kind, issues)
    if isinstance(value, dict):
        if kind == "single-choice-parse-report":
            _validate_report(value, issues)
        elif kind == "single-choice-parse-issues":
            _validate_issues(value, issues)
        else:
            _validate_run(value, issues)
    return issues


def validate_parse_contracts(
    report: Any,
    parse_issues: Any,
    parse_run: Any,
    *,
    artifact_content_hashes: Mapping[str, str] | None = None,
) -> list[ParseContractIssue]:
    issues = validate_parse_document("single-choice-parse-report", report)
    issues.extend(validate_parse_document("single-choice-parse-issues", parse_issues))
    issues.extend(validate_parse_document("single-choice-parse-run", parse_run))

    if isinstance(report, dict) and isinstance(parse_issues, dict) and isinstance(parse_run, dict):
        for name, document in (("parse_issues", parse_issues), ("parse_run", parse_run)):
            if document.get("run_id") != report.get("run_id"):
                _issue(issues, f"cross_document.{name}.run_id", "must match the report run_id")
            if document.get("source_id") != report.get("source_id"):
                _issue(issues, f"cross_document.{name}.source_id", "must match the report source_id")
        if parse_run.get("status") != report.get("status"):
            _issue(issues, "cross_document.parse_run.status", "must match the report status")

        finding_count = report.get("finding_count")
        issue_entries = parse_issues.get("issues")
        if (
            _is_json_schema_integer(finding_count)
            and isinstance(issue_entries, list)
            and finding_count != len(issue_entries)
        ):
            _issue(
                issues,
                "cross_document.parse_issues.issues",
                "cardinality must match the report finding_count",
            )

        report_candidate_path = report.get("candidate_artifact_relative_path")
        report_candidate_hash = report.get("candidate_artifact_content_hash")
        run_artifacts = parse_run.get("artifacts")
        if (
            isinstance(report_candidate_path, str)
            and isinstance(report_candidate_hash, str)
            and isinstance(run_artifacts, list)
        ):
            candidates = [
                artifact
                for artifact in run_artifacts
                if isinstance(artifact, dict) and artifact.get("kind") == "candidate"
            ]
            if len(candidates) == 1:
                candidate = candidates[0]
                if candidate.get("relative_path") != report_candidate_path:
                    _issue(
                        issues,
                        "cross_document.parse_run.artifacts.candidate.relative_path",
                        "must match the report candidate artifact path",
                    )
                if candidate.get("content_hash") != report_candidate_hash:
                    _issue(
                        issues,
                        "cross_document.parse_run.artifacts.candidate.content_hash",
                        "must match the report candidate artifact hash",
                    )

        if artifact_content_hashes is not None:
            artifacts = run_artifacts
            if isinstance(artifacts, list):
                for index, artifact in enumerate(artifacts):
                    if not isinstance(artifact, dict):
                        continue
                    path = artifact.get("relative_path")
                    expected_hash = artifact.get("content_hash")
                    if not isinstance(path, str) or not isinstance(expected_hash, str):
                        continue
                    if artifact_content_hashes.get(path) != expected_hash:
                        _issue(
                            issues,
                            f"cross_document.parse_run.artifacts[{index}].content_hash",
                            "does not match the provided artifact hash",
                        )
    return issues
