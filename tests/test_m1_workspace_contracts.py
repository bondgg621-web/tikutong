from __future__ import annotations

import json
from copy import deepcopy

import jsonschema

from conftest import SKILL_ROOT
from qbcore.workspace_contracts import validate_workspace_document


M1_SCHEMAS = {
    "workspace-project",
    "capability-matrix",
    "discovery-inventory",
    "source-registry",
    "workspace-run",
    "workspace-issues",
    "checkpoint-manifest",
}


def load_schema(name: str) -> dict:
    return json.loads((SKILL_ROOT / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))


def test_every_m1_schema_is_valid_draft_2020_12() -> None:
    for name in M1_SCHEMAS:
        jsonschema.Draft202012Validator.check_schema(load_schema(name))


def test_m1_does_not_change_m0_run_state_semantics() -> None:
    schema = load_schema("run-state")
    assert schema["required"] == ["run_id", "manifest_source_id", "phase", "status"]
    assert schema["properties"]["phase"]["enum"] == [
        "preflight", "candidate", "review", "decision", "complete"
    ]


U1 = "00000000-0000-4000-8000-000000000001"
U2 = "00000000-0000-4000-8000-000000000002"
H1 = "a" * 64
STAMP = "2026-08-13T00:00:00Z"


def valid_documents() -> dict[str, dict]:
    return {
        "workspace-project": {"schema_version": "1.0", "project_format_version": "1.0", "dataset_id": U1, "created_at": STAMP},
        "capability-matrix": {"schema_version": "1.0", "generated_at": STAMP, "skill_version": "0.1.0", "python_version": "3.12.0", "input_root_fingerprint": H1, "workspace_root_fingerprint": H1, "network": {"status": "not_authorized", "attempted": False}, "capabilities": [{"id": "sha256", "status": "available", "detail": "stdlib"}]},
        "discovery-inventory": {"schema_version": "1.0", "generated_at": STAMP, "input_root_fingerprint": H1, "workspace_root_fingerprint": H1, "entries": [{"relative_path": "a.txt", "size_bytes": 1, "content_hash": H1, "support_status": "builtin_text"}], "skipped_directories": [], "issues": []},
        "source-registry": {"schema_version": "1.0", "dataset_id": U1, "registry_revision": 1, "updated_at": STAMP, "sources": [{"source_id": U2, "current_relative_path": "a.txt", "path_history": ["a.txt"], "current_content_hash": H1, "revision": 1, "presence": "present"}]},
        "workspace-run": {"schema_version": "1.0", "run_id": U2, "phase": "complete", "status": "complete", "started_at": STAMP, "updated_at": STAMP, "input_root_fingerprint": H1, "workspace_root_fingerprint": H1, "artifacts": [{"kind": "registry", "relative_path": "registry/sources.json", "content_hash": H1}]},
        "workspace-issues": {"schema_version": "1.0", "run_id": U2, "issues": []},
        "checkpoint-manifest": {"schema_version": "1.0", "checkpoint_id": U2, "created_at": STAMP, "reason": "registry_update", "files": [{"relative_path": "project.json", "content_hash": H1, "size_bytes": 1}]},
    }


def test_valid_samples_pass_runtime_and_json_schema() -> None:
    for kind, value in valid_documents().items():
        assert validate_workspace_document(kind, value) == []
        assert list(jsonschema.Draft202012Validator(load_schema(kind)).iter_errors(value)) == []


def test_runtime_and_json_schema_reject_missing_required_and_unknown_field() -> None:
    for kind, original in valid_documents().items():
        missing = deepcopy(original)
        missing.pop("schema_version")
        assert validate_workspace_document(kind, missing)
        assert list(jsonschema.Draft202012Validator(load_schema(kind)).iter_errors(missing))
        unknown = deepcopy(original)
        unknown["unexpected"] = True
        assert validate_workspace_document(kind, unknown)
        assert list(jsonschema.Draft202012Validator(load_schema(kind)).iter_errors(unknown))


def test_discovery_null_hash_and_size_are_legal_only_for_read_failure() -> None:
    failed = valid_documents()["discovery-inventory"]
    failed["entries"][0].update({"support_status": "read_failed", "content_hash": None, "size_bytes": None})
    assert validate_workspace_document("discovery-inventory", failed) == []
    assert list(jsonschema.Draft202012Validator(load_schema("discovery-inventory")).iter_errors(failed)) == []
    invalid = deepcopy(failed)
    invalid["entries"][0]["support_status"] = "builtin_text"
    assert validate_workspace_document("discovery-inventory", invalid)
    assert list(jsonschema.Draft202012Validator(load_schema("discovery-inventory")).iter_errors(invalid))


def test_runtime_has_no_jsonschema_dependency() -> None:
    source = (SKILL_ROOT / "scripts" / "qbcore" / "workspace_contracts.py").read_text(encoding="utf-8")
    assert "import jsonschema" not in source
    assert "from jsonschema" not in source
