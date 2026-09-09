from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DOCUMENT_KINDS = {
    "workspace-project",
    "capability-matrix",
    "discovery-inventory",
    "source-registry",
    "workspace-run",
    "workspace-issues",
    "checkpoint-manifest",
}


@dataclass(frozen=True)
class WorkspaceContractIssue:
    code: str
    path: str
    message: str


def workspace_schema_path(name: str) -> Path:
    if name not in DOCUMENT_KINDS:
        raise ValueError(f"unknown workspace document kind: {name}")
    return Path(__file__).resolve().parents[2] / "schemas" / f"{name}.schema.json"


def _issue(issues: list[WorkspaceContractIssue], path: str, message: str) -> None:
    issues.append(WorkspaceContractIssue("QB-WORKSPACE-CONTRACT", path, message))


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    raise ValueError(f"unsupported workspace schema type: {expected}")


def _validate_node(
    value: Any,
    schema: dict,
    path: str,
    issues: list[WorkspaceContractIssue],
) -> None:
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
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            _issue(issues, path, "does not match the required pattern")
    if isinstance(value, int) and not isinstance(value, bool):
        if value < schema.get("minimum", value):
            _issue(issues, path, f"must be at least {schema['minimum']}")
    if isinstance(value, dict):
        required = set(schema.get("required", []))
        missing = sorted(required - set(value))
        for key in missing:
            _issue(issues, f"{path}.{key}", "is required")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in sorted(set(value) - set(properties)):
                _issue(issues, f"{path}.{key}", "is not allowed")
        for key, child in properties.items():
            if key in value:
                _validate_node(value[key], child, f"{path}.{key}", issues)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            _issue(issues, path, f"must contain at least {schema['minItems']} item(s)")
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(value):
                _validate_node(item, item_schema, f"{path}[{index}]", issues)


def validate_workspace_document(kind: str, value: Any) -> list[WorkspaceContractIssue]:
    if kind not in DOCUMENT_KINDS:
        raise ValueError(f"unknown workspace document kind: {kind}")
    schema = json.loads(workspace_schema_path(kind).read_text(encoding="utf-8"))
    issues: list[WorkspaceContractIssue] = []
    _validate_node(value, schema, kind, issues)
    if kind == "discovery-inventory" and isinstance(value, dict):
        for index, entry in enumerate(value.get("entries", [])):
            if not isinstance(entry, dict):
                continue
            failed = entry.get("support_status") == "read_failed"
            null_pair = entry.get("content_hash") is None and entry.get("size_bytes") is None
            if failed != null_pair:
                _issue(
                    issues,
                    f"{kind}.entries[{index}]",
                    "only read_failed entries may have null hash and size",
                )
    return issues
