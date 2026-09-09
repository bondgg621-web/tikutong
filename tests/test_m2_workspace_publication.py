from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import os
from pathlib import Path
from uuid import UUID

import pytest

from m2_helpers import UUIDSequence, bootstrap_m1_workspace
from qbcore.candidate_materializer import materialize_candidates
from qbcore.parse_service import (
    ParsePublicationError,
    publish_parse_artifacts,
    resolve_single_choice_source,
)
from qbcore.paths import validate_roots
from qbcore.workspace import Workspace, WorkspaceWriteError


def _bootstrapped_workspace(tmp_path: Path) -> tuple[Workspace, str]:
    bootstrapped = bootstrap_m1_workspace(tmp_path, fixture_names=("strict-two.txt",))
    source_id = bootstrapped.registry["sources"][0]["source_id"]
    workspace = Workspace.initialize(
        validate_roots(bootstrapped.input_root, bootstrapped.workspace_root)
    )
    return workspace, source_id


def _resolved_source(tmp_path: Path):
    bootstrapped = bootstrap_m1_workspace(tmp_path, fixture_names=("strict-two.txt",))
    source_id = bootstrapped.registry["sources"][0]["source_id"]
    resolved = resolve_single_choice_source(
        input_root=bootstrapped.input_root,
        workspace_root=bootstrapped.workspace_root,
        source_id=source_id,
    )
    return bootstrapped, resolved


def _candidate_document(tmp_path: Path) -> tuple[str, dict]:
    bootstrapped, resolved = _resolved_source(tmp_path)
    document = materialize_candidates(
        resolved.parse_result.questions,
        source_id=resolved.source_id,
        uuid_factory=UUIDSequence(100),
    )
    return resolved.source_id, document


def _parse_documents(source_id: str) -> tuple[str, dict, dict, dict]:
    run_id = str(UUID(int=900, version=4))
    report = {
        "schema_version": "1.0",
        "parser_contract_version": "m2-single-choice-v1",
        "run_id": run_id,
        "status": "needs_review",
        "source_id": source_id,
        "source_revision": 1,
        "source_relative_path": "strict-two.txt",
        "source_content_hash": "a" * 64,
        "question_like_block_count": 2,
        "accepted_candidate_count": 0,
        "rejected_block_count": 1,
        "finding_count": 1,
        "candidate_artifact_relative_path": None,
        "candidate_artifact_content_hash": None,
    }
    issues = {
        "schema_version": "1.0",
        "run_id": run_id,
        "source_id": source_id,
        "issues": [
            {
                "issue_id": str(UUID(int=901, version=4)),
                "code": "QB-STRUCTURE-AMBIGUOUS",
                "blocking_level": "review_required",
                "status": "open",
                "source_id": source_id,
                "locator": "line:1",
                "summary": "synthetic summary",
                "allowed_user_actions": ["correct source", "retain", "exclude"],
            }
        ],
    }
    parse_run = {
        "schema_version": "1.0",
        "run_id": run_id,
        "source_id": source_id,
        "phase": "publication",
        "status": "running",
        "started_at": "2026-08-14T00:00:00Z",
        "updated_at": "2026-08-14T00:00:00Z",
        "input_root_fingerprint": "b" * 64,
        "workspace_root_fingerprint": "c" * 64,
        "artifacts": [],
    }
    return run_id, report, issues, parse_run


def _document_hash(document: dict) -> str:
    payload = (
        json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def _successful_publication_documents(tmp_path: Path):
    bootstrapped, resolved = _resolved_source(tmp_path)
    workspace = Workspace.initialize(
        validate_roots(bootstrapped.input_root, bootstrapped.workspace_root)
    )
    run_id = str(UUID(int=950, version=4))
    candidate = materialize_candidates(
        resolved.parse_result.questions,
        source_id=resolved.source_id,
        uuid_factory=UUIDSequence(200),
    )
    candidate_path = f"candidates/sources/{resolved.source_id}.json"
    candidate_hash = _document_hash(candidate)
    report = {
        "schema_version": "1.0",
        "parser_contract_version": "m2-single-choice-v1",
        "run_id": run_id,
        "status": "complete",
        "source_id": resolved.source_id,
        "source_revision": resolved.source_revision,
        "source_relative_path": resolved.relative_path,
        "source_content_hash": resolved.content_hash,
        "question_like_block_count": len(resolved.parse_result.questions),
        "accepted_candidate_count": len(resolved.parse_result.questions),
        "rejected_block_count": 0,
        "finding_count": 0,
        "candidate_artifact_relative_path": candidate_path,
        "candidate_artifact_content_hash": candidate_hash,
    }
    issues = {
        "schema_version": "1.0",
        "run_id": run_id,
        "source_id": resolved.source_id,
        "issues": [],
    }
    artifacts = [
        {
            "kind": "parse_report",
            "relative_path": f"runs/{run_id}/parse-report.json",
            "content_hash": _document_hash(report),
        },
        {
            "kind": "parse_issues",
            "relative_path": f"runs/{run_id}/parse-issues.json",
            "content_hash": _document_hash(issues),
        },
        {
            "kind": "candidate",
            "relative_path": candidate_path,
            "content_hash": candidate_hash,
        },
    ]
    parse_run = {
        "schema_version": "1.0",
        "run_id": run_id,
        "source_id": resolved.source_id,
        "phase": "complete",
        "status": "complete",
        "started_at": "2026-08-14T00:00:00Z",
        "updated_at": "2026-08-14T00:00:01Z",
        "input_root_fingerprint": "b" * 64,
        "workspace_root_fingerprint": "c" * 64,
        "artifacts": artifacts,
    }
    return bootstrapped, workspace, report, issues, parse_run, candidate


def _review_publication_documents(tmp_path: Path):
    workspace, source_id = _bootstrapped_workspace(tmp_path)
    run_id, report, issues, _ = _parse_documents(source_id)
    parse_run = {
        "schema_version": "1.0",
        "run_id": run_id,
        "source_id": source_id,
        "phase": "complete",
        "status": "needs_review",
        "started_at": "2026-08-14T00:00:00Z",
        "updated_at": "2026-08-14T00:00:01Z",
        "input_root_fingerprint": "b" * 64,
        "workspace_root_fingerprint": "c" * 64,
        "artifacts": [
            {
                "kind": "parse_report",
                "relative_path": f"runs/{run_id}/parse-report.json",
                "content_hash": _document_hash(report),
            },
            {
                "kind": "parse_issues",
                "relative_path": f"runs/{run_id}/parse-issues.json",
                "content_hash": _document_hash(issues),
            },
        ],
    }
    return workspace, report, issues, parse_run


class _FaultingBinaryStream:
    def __init__(self, stream, operation: str) -> None:
        self._stream = stream
        self._operation = operation

    def __enter__(self):
        self._stream.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self._stream.__exit__(exc_type, exc_value, traceback)

    def __getattr__(self, name):
        return getattr(self._stream, name)

    def write(self, payload):
        if self._operation == "write":
            raise OSError("injected staging write failure")
        return self._stream.write(payload)

    def flush(self):
        if self._operation == "flush":
            raise OSError("injected staging flush failure")
        return self._stream.flush()


@pytest.mark.parametrize(
    ("name", "kind"),
    (
        ("parse-report.json", "single-choice-parse-report"),
        ("parse-issues.json", "single-choice-parse-issues"),
        ("parse-run.json", "single-choice-parse-run"),
    ),
)
def test_write_parse_run_artifact_uses_only_frozen_names(
    tmp_path: Path,
    name: str,
    kind: str,
) -> None:
    workspace, source_id = _bootstrapped_workspace(tmp_path)
    run_id, report, issues, parse_run = _parse_documents(source_id)
    document = {
        "single-choice-parse-report": report,
        "single-choice-parse-issues": issues,
        "single-choice-parse-run": parse_run,
    }[kind]

    relative_path = workspace.write_parse_run_artifact(run_id, name, document)

    assert relative_path == f"runs/{run_id}/{name}"
    assert json.loads((workspace.root / relative_path).read_text(encoding="utf-8")) == document


@pytest.mark.parametrize(
    "name",
    (
        "../parse-report.json",
        "nested/parse-report.json",
        "nested\\parse-report.json",
        "C:/parse-report.json",
        "parse-report.JSON",
        "workspace-run.json",
    ),
)
def test_write_parse_run_artifact_rejects_unregistered_names(
    tmp_path: Path,
    name: str,
) -> None:
    workspace, source_id = _bootstrapped_workspace(tmp_path)
    run_id, report, _, _ = _parse_documents(source_id)

    with pytest.raises(WorkspaceWriteError, match="parse run artifact name is not allowed"):
        workspace.write_parse_run_artifact(run_id, name, report)


@pytest.mark.parametrize(
    "run_id",
    (
        "not-a-uuid",
        "00000000-0000-4000-8000-00000000000A",
        "../00000000-0000-4000-8000-000000000001",
    ),
)
def test_write_parse_run_artifact_rejects_invalid_run_id(
    tmp_path: Path,
    run_id: str,
) -> None:
    workspace, source_id = _bootstrapped_workspace(tmp_path)
    _, report, _, _ = _parse_documents(source_id)

    with pytest.raises(WorkspaceWriteError, match="run_id must be a lowercase UUID"):
        workspace.write_parse_run_artifact(run_id, "parse-report.json", report)


@pytest.mark.parametrize(
    "name",
    ("parse-report.json", "parse-issues.json", "parse-run.json"),
)
def test_m1_generic_run_allowlist_does_not_accept_m2_artifact_names(
    tmp_path: Path,
    name: str,
) -> None:
    workspace, source_id = _bootstrapped_workspace(tmp_path)
    run_id, report, _, _ = _parse_documents(source_id)

    with pytest.raises(WorkspaceWriteError, match="run artifact name is not allowed"):
        workspace.write_run_artifact(run_id, name, report)


@pytest.mark.parametrize(
    "source_id",
    (
        "../escape",
        "00000000-0000-4000-8000-00000000000A",
        "00000000-0000-4000-8000-000000000001/extra",
    ),
)
def test_publish_candidate_source_requires_exact_source_uuid_name(
    tmp_path: Path,
    source_id: str,
) -> None:
    workspace, _ = _bootstrapped_workspace(tmp_path)
    _, document = _candidate_document(tmp_path / "candidate")

    with pytest.raises(WorkspaceWriteError, match="source_id must be a lowercase UUID"):
        workspace.publish_candidate_source(source_id, document)


def test_publish_candidate_source_uses_frozen_target_and_round_trips(tmp_path: Path) -> None:
    workspace, source_id = _bootstrapped_workspace(tmp_path / "workspace-case")
    _, document = _candidate_document(tmp_path / "candidate-case")

    relative_path, content_hash = workspace.publish_candidate_source(source_id, document)

    assert relative_path == f"candidates/sources/{source_id}.json"
    target = workspace.root / relative_path
    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == document
    assert len(content_hash) == 64


def test_workspace_rejects_candidate_bound_to_a_different_source(
    tmp_path: Path,
) -> None:
    workspace, source_id = _bootstrapped_workspace(tmp_path / "workspace-case")
    _, document = _candidate_document(tmp_path / "candidate-case")
    other_source_id = str(UUID(int=999, version=4))
    for candidate in document["candidates"]:
        candidate["source_id"] = other_source_id
        for option in candidate["options"]:
            option["source_ref"]["source_id"] = other_source_id

    with pytest.raises(WorkspaceWriteError, match="candidate source does not match"):
        workspace.publish_candidate_source(source_id, document)

    target = workspace.root / "candidates" / "sources" / f"{source_id}.json"
    assert not target.exists()


def test_publish_candidate_source_fails_closed_when_target_exists(tmp_path: Path) -> None:
    workspace, source_id = _bootstrapped_workspace(tmp_path / "workspace-case")
    _, document = _candidate_document(tmp_path / "candidate-case")
    relative_path, content_hash = workspace.publish_candidate_source(source_id, document)
    target = workspace.root / relative_path
    before_bytes = target.read_bytes()

    with pytest.raises(WorkspaceWriteError, match="candidate artifact already exists"):
        workspace.publish_candidate_source(source_id, document)

    assert target.read_bytes() == before_bytes
    assert len(content_hash) == 64


def test_write_parse_run_artifact_rejects_invalid_contract_before_creating_target(
    tmp_path: Path,
) -> None:
    workspace, source_id = _bootstrapped_workspace(tmp_path)
    run_id, report, _, _ = _parse_documents(source_id)
    report.pop("schema_version")
    target = workspace.root / "runs" / run_id / "parse-report.json"

    with pytest.raises(WorkspaceWriteError, match="invalid single-choice-parse-report"):
        workspace.write_parse_run_artifact(run_id, "parse-report.json", report)

    assert not target.exists()


def test_injected_candidate_publish_failure_cleans_staging_and_preserves_absence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, source_id = _bootstrapped_workspace(tmp_path / "workspace-case")
    _, document = _candidate_document(tmp_path / "candidate-case")
    target = workspace.root / "candidates" / "sources" / f"{source_id}.json"

    monkeypatch.setattr(
        "qbcore.workspace.os.link",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("injected")),
    )
    with pytest.raises(WorkspaceWriteError, match="candidate artifact publication failed"):
        workspace.publish_candidate_source(source_id, document)

    assert not target.exists()
    assert list(target.parent.glob("*.tmp")) == []


def test_concurrent_candidate_publication_has_exactly_one_winner(tmp_path: Path) -> None:
    workspace, source_id = _bootstrapped_workspace(tmp_path / "workspace-case")
    _, document = _candidate_document(tmp_path / "candidate-case")

    def publish() -> str:
        try:
            workspace.publish_candidate_source(source_id, document)
        except WorkspaceWriteError:
            return "rejected"
        return "published"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: publish(), range(2)))

    assert sorted(results) == ["published", "rejected"]
    target = workspace.root / "candidates" / "sources" / f"{source_id}.json"
    assert json.loads(target.read_text(encoding="utf-8")) == document
    assert list(target.parent.glob("*.tmp")) == []


@pytest.mark.skipif(os.name != "nt", reason="Windows no-overwrite primitive probe")
def test_windows_hard_link_probe_does_not_replace_existing_target(tmp_path: Path) -> None:
    staging = tmp_path / "staging.json"
    target = tmp_path / "target.json"
    staging.write_bytes(b'{"new":true}\n')
    target.write_bytes(b'{"existing":true}\n')

    with pytest.raises(FileExistsError):
        os.link(staging, target)

    assert target.read_bytes() == b'{"existing":true}\n'


def test_successful_publication_finishes_only_after_candidate_read_back(
    tmp_path: Path,
) -> None:
    _, workspace, report, issues, parse_run, candidate = _successful_publication_documents(
        tmp_path
    )

    publish_parse_artifacts(
        workspace=workspace,
        report=report,
        parse_issues=issues,
        parse_run=parse_run,
        candidate_document=candidate,
    )

    candidate_path = workspace.root / report["candidate_artifact_relative_path"]
    run_path = workspace.root / "runs" / report["run_id"] / "parse-run.json"
    assert json.loads(candidate_path.read_text(encoding="utf-8")) == candidate
    assert json.loads(run_path.read_text(encoding="utf-8")) == parse_run


def test_needs_review_publication_writes_diagnostics_without_candidate(
    tmp_path: Path,
) -> None:
    workspace, report, issues, parse_run = _review_publication_documents(tmp_path)

    publish_parse_artifacts(
        workspace=workspace,
        report=report,
        parse_issues=issues,
        parse_run=parse_run,
        candidate_document=None,
    )

    run_root = workspace.root / "runs" / report["run_id"]
    assert json.loads((run_root / "parse-report.json").read_text(encoding="utf-8")) == report
    assert json.loads((run_root / "parse-issues.json").read_text(encoding="utf-8")) == issues
    assert json.loads((run_root / "parse-run.json").read_text(encoding="utf-8")) == parse_run
    assert not (workspace.root / "candidates").exists()


def test_run_artifact_failure_discards_staging_and_does_not_publish_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrapped, workspace, report, issues, parse_run, candidate = (
        _successful_publication_documents(tmp_path)
    )
    registry_path = workspace.root / "registry" / "sources.json"
    registry_before = registry_path.read_bytes()
    original_replace = os.replace

    def fail_on_issues(source, target):
        if Path(target).name == "parse-issues.json":
            raise OSError("injected run artifact publication failure")
        return original_replace(source, target)

    monkeypatch.setattr("qbcore.workspace.os.replace", fail_on_issues)
    with pytest.raises(ParsePublicationError, match="parse artifact publication failed"):
        publish_parse_artifacts(
            workspace=workspace,
            report=report,
            parse_issues=issues,
            parse_run=parse_run,
            candidate_document=candidate,
        )

    candidate_path = workspace.root / report["candidate_artifact_relative_path"]
    assert not candidate_path.exists()
    assert list(candidate_path.parent.glob("*.tmp")) == []
    run_root = workspace.root / "runs" / report["run_id"]
    assert json.loads((run_root / "parse-report.json").read_text(encoding="utf-8")) == report
    assert not (run_root / "parse-issues.json").exists()
    assert list(run_root.glob("*.tmp")) == []
    assert registry_path.read_bytes() == registry_before
    assert bootstrapped.registry == json.loads(registry_path.read_text(encoding="utf-8"))


def test_candidate_read_back_failure_leaves_candidate_and_publication_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, workspace, report, issues, parse_run, candidate = _successful_publication_documents(
        tmp_path
    )
    target = workspace.root / report["candidate_artifact_relative_path"]
    registry_path = workspace.root / "registry" / "sources.json"
    registry_before = registry_path.read_bytes()
    expected_candidate_hash = _document_hash(candidate)
    original_read_bytes = Path.read_bytes

    def fail_candidate_read_back(path: Path) -> bytes:
        if path == target:
            raise OSError("injected candidate read-back failure")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", fail_candidate_read_back)
    with pytest.raises(ParsePublicationError, match="parse artifact publication failed"):
        publish_parse_artifacts(
            workspace=workspace,
            report=report,
            parse_issues=issues,
            parse_run=parse_run,
            candidate_document=candidate,
        )

    monkeypatch.setattr(Path, "read_bytes", original_read_bytes)
    run_path = workspace.root / "runs" / report["run_id"] / "parse-run.json"
    persisted_run = json.loads(run_path.read_text(encoding="utf-8"))
    candidate_bytes = original_read_bytes(target)
    assert sha256(candidate_bytes).hexdigest() == expected_candidate_hash
    assert json.loads(candidate_bytes.decode("utf-8")) == candidate
    assert registry_path.read_bytes() == registry_before
    assert persisted_run["phase"] == "publication"
    assert persisted_run["status"] == "running"


def test_final_run_update_failure_leaves_recoverable_publication_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, workspace, report, issues, parse_run, candidate = _successful_publication_documents(
        tmp_path
    )
    original = Workspace.write_parse_run_artifact

    def fail_final_update(self, run_id, name, document):
        if name == "parse-run.json" and document.get("phase") == "complete":
            raise WorkspaceWriteError("injected final run failure")
        return original(self, run_id, name, document)

    monkeypatch.setattr(Workspace, "write_parse_run_artifact", fail_final_update)
    with pytest.raises(ParsePublicationError, match="parse artifact publication failed"):
        publish_parse_artifacts(
            workspace=workspace,
            report=report,
            parse_issues=issues,
            parse_run=parse_run,
            candidate_document=candidate,
        )

    target = workspace.root / report["candidate_artifact_relative_path"]
    run_path = workspace.root / "runs" / report["run_id"] / "parse-run.json"
    persisted_run = json.loads(run_path.read_text(encoding="utf-8"))
    assert json.loads(target.read_text(encoding="utf-8")) == candidate
    assert persisted_run["phase"] == "publication"
    assert persisted_run["status"] == "running"


@pytest.mark.parametrize(
    "boundary",
    ("create", "write", "flush", "fsync", "read_back"),
)
def test_candidate_staging_failure_prevents_any_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
) -> None:
    _, workspace, report, issues, parse_run, candidate = _successful_publication_documents(
        tmp_path
    )
    registry_path = workspace.root / "registry" / "sources.json"
    registry_before = registry_path.read_bytes()
    original_open = Path.open
    original_read_bytes = Path.read_bytes

    if boundary in {"create", "write", "flush"}:
        def faulting_open(path: Path, mode="r", *args, **kwargs):
            if mode == "xb" and path.name.endswith(".tmp"):
                if boundary == "create":
                    raise OSError("injected staging create failure")
                return _FaultingBinaryStream(
                    original_open(path, mode, *args, **kwargs),
                    boundary,
                )
            return original_open(path, mode, *args, **kwargs)

        monkeypatch.setattr(Path, "open", faulting_open)
    elif boundary == "fsync":
        monkeypatch.setattr(
            "qbcore.workspace.os.fsync",
            lambda _file_descriptor: (_ for _ in ()).throw(
                OSError("injected staging fsync failure")
            ),
        )
    else:
        def faulting_read_bytes(path: Path) -> bytes:
            if path.name.endswith(".tmp"):
                raise OSError("injected staging read-back failure")
            return original_read_bytes(path)

        monkeypatch.setattr(Path, "read_bytes", faulting_read_bytes)

    with pytest.raises(ParsePublicationError, match="parse artifact publication failed"):
        publish_parse_artifacts(
            workspace=workspace,
            report=report,
            parse_issues=issues,
            parse_run=parse_run,
            candidate_document=candidate,
        )

    candidate_path = workspace.root / report["candidate_artifact_relative_path"]
    assert not candidate_path.exists()
    assert not (workspace.root / "runs" / report["run_id"]).exists()
    assert list(candidate_path.parent.glob("*.tmp")) == []
    assert registry_path.read_bytes() == registry_before


def test_no_overwrite_failure_preserves_candidate_and_publication_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, workspace, report, issues, parse_run, candidate = _successful_publication_documents(
        tmp_path
    )
    relative_path, _ = workspace.publish_candidate_source(report["source_id"], candidate)
    target = workspace.root / relative_path
    candidate_before = target.read_bytes()
    registry_path = workspace.root / "registry" / "sources.json"
    registry_before = registry_path.read_bytes()
    monkeypatch.setattr(
        Workspace,
        "assert_candidate_source_absent",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(ParsePublicationError, match="parse artifact publication failed"):
        publish_parse_artifacts(
            workspace=workspace,
            report=report,
            parse_issues=issues,
            parse_run=parse_run,
            candidate_document=candidate,
        )

    run_path = workspace.root / "runs" / report["run_id"] / "parse-run.json"
    persisted_run = json.loads(run_path.read_text(encoding="utf-8"))
    assert target.read_bytes() == candidate_before
    assert registry_path.read_bytes() == registry_before
    assert persisted_run["phase"] == "publication"
    assert persisted_run["status"] == "running"
    assert list(target.parent.glob("*.tmp")) == []


def test_forged_prepared_candidate_cannot_escape_frozen_candidate_target(
    tmp_path: Path,
) -> None:
    workspace, source_id = _bootstrapped_workspace(tmp_path / "workspace-case")
    _, document = _candidate_document(tmp_path / "candidate-case")
    prepared = workspace.prepare_candidate_source(source_id, document)
    forged_target = workspace.root / "registry" / "forged.json"
    forged = replace(
        prepared,
        target_path=forged_target,
        relative_path="registry/forged.json",
    )

    with pytest.raises(WorkspaceWriteError, match="prepared candidate target is invalid"):
        workspace.publish_prepared_candidate_source(forged)

    assert not forged_target.exists()
    assert not prepared.temporary_path.exists()


def test_parse_run_artifact_reports_final_read_back_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, source_id = _bootstrapped_workspace(tmp_path)
    run_id, report, _, _ = _parse_documents(source_id)
    target = workspace.root / "runs" / run_id / "parse-report.json"
    original_read_bytes = Path.read_bytes

    def mismatched_read_back(path: Path) -> bytes:
        if path == target:
            return b"{}\n"
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", mismatched_read_back)
    with pytest.raises(WorkspaceWriteError, match="parse run artifact read-back failed"):
        workspace.write_parse_run_artifact(run_id, "parse-report.json", report)

    assert not target.exists()


def test_parse_run_update_restores_previous_bytes_after_read_back_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, report, _, terminal_run = _review_publication_documents(tmp_path)
    run_id = report["run_id"]
    publication_run = deepcopy(terminal_run)
    publication_run["phase"] = "publication"
    publication_run["status"] = "running"
    target = workspace.root / "runs" / run_id / "parse-run.json"
    workspace.write_parse_run_artifact(run_id, "parse-run.json", publication_run)
    previous_bytes = target.read_bytes()
    original_read_bytes = Path.read_bytes

    def mismatched_read_back(path: Path) -> bytes:
        if path == target:
            return b"{}\n"
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", mismatched_read_back)
    with pytest.raises(WorkspaceWriteError, match="parse run artifact read-back failed"):
        workspace.write_parse_run_artifact(run_id, "parse-run.json", terminal_run)

    assert original_read_bytes(target) == previous_bytes


def test_invalid_publication_contract_is_rejected_before_candidate_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, workspace, report, issues, parse_run, candidate = _successful_publication_documents(
        tmp_path
    )
    report["accepted_candidate_count"] = 0

    def unexpected_staging(*_args, **_kwargs):
        raise AssertionError("candidate staging must not begin")

    monkeypatch.setattr(Workspace, "prepare_candidate_source", unexpected_staging)
    with pytest.raises(ParsePublicationError, match="invalid parse publication contract"):
        publish_parse_artifacts(
            workspace=workspace,
            report=report,
            parse_issues=issues,
            parse_run=parse_run,
            candidate_document=candidate,
        )


def test_tampered_candidate_staging_never_becomes_authoritative(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, source_id = _bootstrapped_workspace(tmp_path / "workspace-case")
    _, document = _candidate_document(tmp_path / "candidate-case")
    prepared = workspace.prepare_candidate_source(source_id, document)
    prepared.temporary_path.write_bytes(b"{}\n")
    monkeypatch.setattr(
        "qbcore.workspace.os.link",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("invalid staging must not reach publication")
        ),
    )

    with pytest.raises(WorkspaceWriteError, match="candidate artifact read-back"):
        workspace.publish_prepared_candidate_source(prepared)

    assert not prepared.target_path.exists()
    assert not prepared.temporary_path.exists()


@pytest.mark.parametrize("mismatch", ("source", "count"))
def test_candidate_must_match_report_source_and_count_before_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    _, workspace, report, issues, parse_run, candidate = _successful_publication_documents(
        tmp_path
    )
    invalid_candidate = deepcopy(candidate)
    if mismatch == "source":
        other_source_id = str(UUID(int=999, version=4))
        for item in invalid_candidate["candidates"]:
            item["source_id"] = other_source_id
            for option in item["options"]:
                option["source_ref"]["source_id"] = other_source_id
    else:
        invalid_candidate["candidates"] = invalid_candidate["candidates"][:1]

    def unexpected_staging(*_args, **_kwargs):
        raise AssertionError("mismatched candidate must not be staged")

    monkeypatch.setattr(Workspace, "prepare_candidate_source", unexpected_staging)
    with pytest.raises(ParsePublicationError, match="candidate document does not match"):
        publish_parse_artifacts(
            workspace=workspace,
            report=report,
            parse_issues=issues,
            parse_run=parse_run,
            candidate_document=invalid_candidate,
        )


def test_repeating_completed_publication_preserves_all_authoritative_bytes(
    tmp_path: Path,
) -> None:
    _, workspace, report, issues, parse_run, candidate = _successful_publication_documents(
        tmp_path
    )
    publish_parse_artifacts(
        workspace=workspace,
        report=report,
        parse_issues=issues,
        parse_run=parse_run,
        candidate_document=candidate,
    )
    paths = (
        workspace.root / report["candidate_artifact_relative_path"],
        workspace.root / "runs" / report["run_id"] / "parse-report.json",
        workspace.root / "runs" / report["run_id"] / "parse-issues.json",
        workspace.root / "runs" / report["run_id"] / "parse-run.json",
        workspace.root / "registry" / "sources.json",
    )
    before = {path: path.read_bytes() for path in paths}

    with pytest.raises(ParsePublicationError, match="parse artifact publication failed"):
        publish_parse_artifacts(
            workspace=workspace,
            report=report,
            parse_issues=issues,
            parse_run=parse_run,
            candidate_document=candidate,
        )

    assert {path: path.read_bytes() for path in paths} == before


def test_publication_hides_workspace_error_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, workspace, report, issues, parse_run, candidate = _successful_publication_documents(
        tmp_path
    )

    def fail_with_host_path(*_args, **_kwargs):
        raise WorkspaceWriteError(r"injected D:\private\workspace failure")

    monkeypatch.setattr(Workspace, "write_parse_run_artifact", fail_with_host_path)
    with pytest.raises(ParsePublicationError, match="parse artifact publication failed") as exc:
        publish_parse_artifacts(
            workspace=workspace,
            report=report,
            parse_issues=issues,
            parse_run=parse_run,
            candidate_document=candidate,
        )

    assert "private" not in str(exc.value)


def test_staging_cleanup_failure_does_not_mask_publication_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, workspace, report, issues, parse_run, candidate = _successful_publication_documents(
        tmp_path
    )

    monkeypatch.setattr(
        Workspace,
        "write_parse_run_artifact",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            WorkspaceWriteError("primary publication failure")
        ),
    )
    monkeypatch.setattr(
        Workspace,
        "discard_prepared_candidate_source",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            WorkspaceWriteError("secondary cleanup failure")
        ),
    )

    with pytest.raises(ParsePublicationError, match="parse artifact publication failed") as exc:
        publish_parse_artifacts(
            workspace=workspace,
            report=report,
            parse_issues=issues,
            parse_run=parse_run,
            candidate_document=candidate,
        )

    assert "cleanup" not in str(exc.value)


def test_contract_loader_failure_is_sanitized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, workspace, report, issues, parse_run, candidate = _successful_publication_documents(
        tmp_path
    )
    monkeypatch.setattr(
        "qbcore.parse_service.validate_parse_contracts",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            FileNotFoundError(r"D:\private\missing-schema.json")
        ),
    )

    with pytest.raises(
        ParsePublicationError,
        match="parse publication contract validation failed",
    ) as exc:
        publish_parse_artifacts(
            workspace=workspace,
            report=report,
            parse_issues=issues,
            parse_run=parse_run,
            candidate_document=candidate,
        )

    assert "private" not in str(exc.value)


def test_rollback_snapshot_cleanup_failure_does_not_misreport_committed_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, workspace, report, issues, parse_run, candidate = _successful_publication_documents(
        tmp_path
    )
    original_unlink = Path.unlink

    def fail_rollback_cleanup(path: Path, *args, **kwargs):
        if path.name.endswith(".rollback"):
            raise OSError("injected rollback cleanup failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_rollback_cleanup)
    publish_parse_artifacts(
        workspace=workspace,
        report=report,
        parse_issues=issues,
        parse_run=parse_run,
        candidate_document=candidate,
    )

    run_root = workspace.root / "runs" / report["run_id"]
    persisted_run = json.loads((run_root / "parse-run.json").read_text(encoding="utf-8"))
    assert persisted_run["status"] == "complete"
    assert (workspace.root / report["candidate_artifact_relative_path"]).exists()
    assert list(run_root.glob("*.rollback"))
