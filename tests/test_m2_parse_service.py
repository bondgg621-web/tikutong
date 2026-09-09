from __future__ import annotations

import json
from pathlib import Path

import pytest

from m2_helpers import UUIDSequence, bootstrap_m1_workspace, fixed_now
from qbcore.parse_service import (
    ParsePublicationError,
    ParseServiceError,
    SourceResolutionError,
    run_single_choice_parse,
)
from qbcore.workspace import Workspace, WorkspaceWriteError


def _source_id(bootstrapped) -> str:
    return bootstrapped.registry["sources"][0]["source_id"]


def _run(
    bootstrapped,
    *,
    uuid_factory,
):
    return run_single_choice_parse(
        input_root=bootstrapped.input_root,
        workspace_root=bootstrapped.workspace_root,
        source_id=_source_id(bootstrapped),
        now=fixed_now,
        uuid_factory=uuid_factory,
    )


def _unexpected_uuid():
    raise AssertionError("UUID allocation must not occur")


def _write_json(path: Path, document: dict) -> None:
    path.write_text(
        json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def test_service_success_publishes_candidate_and_complete_artifacts(tmp_path: Path) -> None:
    bootstrapped = bootstrap_m1_workspace(
        tmp_path,
        fixture_names=("strict-two.txt",),
    )

    result = _run(bootstrapped, uuid_factory=UUIDSequence(1000))

    assert result.status == "complete"
    run_root = bootstrapped.workspace_root / "runs" / result.run_id
    report = json.loads((run_root / "parse-report.json").read_text(encoding="utf-8"))
    issues = json.loads((run_root / "parse-issues.json").read_text(encoding="utf-8"))
    parse_run = json.loads((run_root / "parse-run.json").read_text(encoding="utf-8"))
    candidate_path = bootstrapped.workspace_root / report["candidate_artifact_relative_path"]
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    assert report["status"] == "complete"
    assert report["accepted_candidate_count"] == 2
    assert issues["issues"] == []
    assert parse_run["phase"] == "complete"
    assert parse_run["status"] == "complete"
    assert len(candidate["candidates"]) == 2
    assert {item["status"] for item in candidate["candidates"]} == {"candidate"}
    serialized = json.dumps(candidate, sort_keys=True)
    assert all(token not in serialized for token in ("answer", "correct", "decision", "resolved_option"))


@pytest.mark.parametrize(
    ("fixture_name", "expected_code"),
    (
        ("malformed.md", "QB-STRUCTURE-AMBIGUOUS"),
        ("unsupported-type.md", "QB-TYPE-UNSUPPORTED"),
    ),
)
def test_service_findings_publish_needs_review_without_candidate(
    tmp_path: Path,
    fixture_name: str,
    expected_code: str,
) -> None:
    bootstrapped = bootstrap_m1_workspace(tmp_path, fixture_names=(fixture_name,))

    result = _run(bootstrapped, uuid_factory=UUIDSequence(1100))

    assert result.status == "needs_review"
    run_root = bootstrapped.workspace_root / "runs" / result.run_id
    report = json.loads((run_root / "parse-report.json").read_text(encoding="utf-8"))
    issues = json.loads((run_root / "parse-issues.json").read_text(encoding="utf-8"))
    parse_run = json.loads((run_root / "parse-run.json").read_text(encoding="utf-8"))
    assert report["status"] == "needs_review"
    assert {issue["code"] for issue in issues["issues"]} == {expected_code}
    assert parse_run["status"] == "needs_review"
    assert not (bootstrapped.workspace_root / "candidates").exists()


def test_service_no_questions_publishes_sanitized_needs_review_issue(tmp_path: Path) -> None:
    bootstrapped = bootstrap_m1_workspace(
        tmp_path,
        fixture_names=("strict-two.txt",),
    )
    source = bootstrapped.input_root / "strict-two.txt"
    source.write_text("# Notes\n\nOrdinary prose only.\n", encoding="utf-8")
    # Refresh the registry so the no-question content is the authorized snapshot.
    from qbcore.cli import run_inventory

    run_inventory(
        input_root=bootstrapped.input_root,
        workspace_root=bootstrapped.workspace_root,
        now=fixed_now,
        uuid_factory=UUIDSequence(1200),
    )

    result = _run(bootstrapped, uuid_factory=UUIDSequence(1300))

    run_root = bootstrapped.workspace_root / "runs" / result.run_id
    report = json.loads((run_root / "parse-report.json").read_text(encoding="utf-8"))
    issues = json.loads((run_root / "parse-issues.json").read_text(encoding="utf-8"))
    assert result.status == "needs_review"
    assert report["question_like_block_count"] == 0
    assert report["accepted_candidate_count"] == 0
    assert len(issues["issues"]) == 1
    assert issues["issues"][0]["code"] == "QB-STRUCTURE-AMBIGUOUS"
    assert "Ordinary prose" not in issues["issues"][0]["summary"]
    assert not (bootstrapped.workspace_root / "candidates").exists()


@pytest.mark.parametrize("corrupted", (False, True))
def test_existing_candidate_fails_closed_without_uuid_allocation_or_mutation(
    tmp_path: Path,
    corrupted: bool,
) -> None:
    bootstrapped = bootstrap_m1_workspace(
        tmp_path,
        fixture_names=("strict-two.txt",),
    )
    if corrupted:
        target = (
            bootstrapped.workspace_root
            / "candidates"
            / "sources"
            / f"{_source_id(bootstrapped)}.json"
        )
        target.parent.mkdir(parents=True)
        target.write_bytes(b'{"corrupted":true}\n')
    else:
        _run(bootstrapped, uuid_factory=UUIDSequence(1400))
        target = (
            bootstrapped.workspace_root
            / "candidates"
            / "sources"
            / f"{_source_id(bootstrapped)}.json"
        )
    before = target.read_bytes()
    runs_before = {
        path.relative_to(bootstrapped.workspace_root).as_posix(): path.read_bytes()
        for path in bootstrapped.workspace_root.glob("runs/*/*.json")
    }

    with pytest.raises(ParseServiceError) as exc:
        _run(bootstrapped, uuid_factory=_unexpected_uuid)

    assert exc.value.issue_code == "QB-IDENTITY-AMBIGUOUS"
    assert target.read_bytes() == before
    assert {
        path.relative_to(bootstrapped.workspace_root).as_posix(): path.read_bytes()
        for path in bootstrapped.workspace_root.glob("runs/*/*.json")
    } == runs_before


def test_schema_valid_candidate_tampering_is_detected_against_complete_run_hash(
    tmp_path: Path,
) -> None:
    bootstrapped = bootstrap_m1_workspace(
        tmp_path,
        fixture_names=("strict-two.txt",),
    )
    _run(bootstrapped, uuid_factory=UUIDSequence(1450))
    target = (
        bootstrapped.workspace_root
        / "candidates"
        / "sources"
        / f"{_source_id(bootstrapped)}.json"
    )
    candidate = json.loads(target.read_text(encoding="utf-8"))
    candidate["candidates"][0]["stem"] = "Schema-valid tampered stem"
    target.write_text(
        json.dumps(candidate, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    before = target.read_bytes()

    with pytest.raises(ParseServiceError, match="does not match its completed run") as exc:
        _run(bootstrapped, uuid_factory=_unexpected_uuid)

    assert exc.value.issue_code == "QB-IDENTITY-AMBIGUOUS"
    assert target.read_bytes() == before


def test_existing_candidate_is_checked_before_source_text_is_parsed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrapped = bootstrap_m1_workspace(
        tmp_path,
        fixture_names=("strict-two.txt",),
    )
    _run(bootstrapped, uuid_factory=UUIDSequence(1475))
    monkeypatch.setattr(
        "qbcore.parse_service.parse_single_choice",
        lambda _text: (_ for _ in ()).throw(
            AssertionError("existing candidate must be checked before parsing")
        ),
    )

    with pytest.raises(ParseServiceError):
        _run(bootstrapped, uuid_factory=_unexpected_uuid)


def test_stale_source_fails_before_uuid_allocation_and_writes(tmp_path: Path) -> None:
    bootstrapped = bootstrap_m1_workspace(
        tmp_path,
        fixture_names=("strict-two.txt",),
    )
    (bootstrapped.input_root / "strict-two.txt").write_text(
        "changed after inventory\n",
        encoding="utf-8",
    )
    before = {
        path.relative_to(bootstrapped.workspace_root).as_posix(): path.read_bytes()
        for path in bootstrapped.workspace_root.rglob("*")
        if path.is_file()
    }

    with pytest.raises(SourceResolutionError, match="stale"):
        _run(bootstrapped, uuid_factory=_unexpected_uuid)

    assert {
        path.relative_to(bootstrapped.workspace_root).as_posix(): path.read_bytes()
        for path in bootstrapped.workspace_root.rglob("*")
        if path.is_file()
    } == before


def test_existing_candidate_with_exact_incomplete_run_repairs_only_run_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrapped = bootstrap_m1_workspace(
        tmp_path,
        fixture_names=("strict-two.txt",),
    )
    original = Workspace.write_parse_run_artifact

    def fail_final_update(self, run_id, name, document):
        if name == "parse-run.json" and document.get("phase") == "complete":
            raise WorkspaceWriteError("injected final update failure")
        return original(self, run_id, name, document)

    monkeypatch.setattr(Workspace, "write_parse_run_artifact", fail_final_update)
    with pytest.raises(ParsePublicationError):
        _run(bootstrapped, uuid_factory=UUIDSequence(1500))
    monkeypatch.setattr(Workspace, "write_parse_run_artifact", original)

    candidate_path = (
        bootstrapped.workspace_root
        / "candidates"
        / "sources"
        / f"{_source_id(bootstrapped)}.json"
    )
    candidate_before = candidate_path.read_bytes()
    publication_runs = []
    for path in bootstrapped.workspace_root.glob("runs/*/parse-run.json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("phase") == "publication":
            publication_runs.append((path, document))
    assert len(publication_runs) == 1
    run_path, publication_run = publication_runs[0]
    other_before = {
        path.relative_to(bootstrapped.workspace_root).as_posix(): path.read_bytes()
        for path in bootstrapped.workspace_root.rglob("*")
        if path.is_file() and path != run_path
    }

    result = _run(bootstrapped, uuid_factory=_unexpected_uuid)

    repaired = json.loads(run_path.read_text(encoding="utf-8"))
    assert result.run_id == publication_run["run_id"]
    assert result.status == "complete"
    assert repaired["phase"] == "complete"
    assert repaired["status"] == "complete"
    assert candidate_path.read_bytes() == candidate_before
    assert {
        path.relative_to(bootstrapped.workspace_root).as_posix(): path.read_bytes()
        for path in bootstrapped.workspace_root.rglob("*")
        if path.is_file() and path != run_path
    } == other_before


@pytest.mark.parametrize(
    "mismatch",
    (
        "candidate_path",
        "candidate_hash",
        "source_id",
        "source_revision",
        "source_relative_path",
        "source_content_hash",
        "contract",
    ),
)
def test_incomplete_run_mismatch_fails_without_uuid_or_file_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    bootstrapped = bootstrap_m1_workspace(
        tmp_path,
        fixture_names=("strict-two.txt",),
    )
    original = Workspace.write_parse_run_artifact

    def fail_final_update(self, run_id, name, document):
        if name == "parse-run.json" and document.get("phase") == "complete":
            raise WorkspaceWriteError("injected final update failure")
        return original(self, run_id, name, document)

    monkeypatch.setattr(Workspace, "write_parse_run_artifact", fail_final_update)
    with pytest.raises(ParsePublicationError):
        _run(bootstrapped, uuid_factory=UUIDSequence(1600))
    monkeypatch.setattr(Workspace, "write_parse_run_artifact", original)

    run_path = next(
        path
        for path in bootstrapped.workspace_root.glob("runs/*/parse-run.json")
        if json.loads(path.read_text(encoding="utf-8")).get("phase") == "publication"
    )
    report_path = run_path.parent / "parse-report.json"
    issues_path = run_path.parent / "parse-issues.json"
    parse_run = json.loads(run_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    issues = json.loads(issues_path.read_text(encoding="utf-8"))
    if mismatch == "candidate_path":
        report["candidate_artifact_relative_path"] = "candidates/sources/00000000-0000-4000-8000-000000000999.json"
        _write_json(report_path, report)
    elif mismatch == "candidate_hash":
        report["candidate_artifact_content_hash"] = "d" * 64
        next(
            item for item in parse_run["artifacts"] if item["kind"] == "candidate"
        )["content_hash"] = "d" * 64
        _write_json(report_path, report)
        _write_json(run_path, parse_run)
    elif mismatch == "source_id":
        other_source_id = str(UUIDSequence(1700)())
        report["source_id"] = other_source_id
        issues["source_id"] = other_source_id
        parse_run["source_id"] = other_source_id
        _write_json(report_path, report)
        _write_json(issues_path, issues)
        _write_json(run_path, parse_run)
    elif mismatch == "source_revision":
        report["source_revision"] += 1
        _write_json(report_path, report)
    elif mismatch == "source_relative_path":
        moved_relative_path = "moved/strict-two.txt"
        moved_source = bootstrapped.input_root / moved_relative_path
        moved_source.parent.mkdir(parents=True)
        moved_source.write_bytes(
            (bootstrapped.input_root / report["source_relative_path"]).read_bytes()
        )
        registry_path = (
            bootstrapped.workspace_root / "registry" / "sources.json"
        )
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        next(
            source
            for source in registry["sources"]
            if source["source_id"] == report["source_id"]
        )["current_relative_path"] = moved_relative_path
        _write_json(registry_path, registry)
    elif mismatch == "source_content_hash":
        report["source_content_hash"] = "e" * 64
        _write_json(report_path, report)
    else:
        issues.pop("schema_version")
        _write_json(issues_path, issues)

    before = {
        path.relative_to(bootstrapped.workspace_root).as_posix(): path.read_bytes()
        for path in bootstrapped.workspace_root.rglob("*")
        if path.is_file()
    }
    with pytest.raises(ParseServiceError) as exc:
        _run(bootstrapped, uuid_factory=_unexpected_uuid)

    assert exc.value.issue_code == "QB-IDENTITY-AMBIGUOUS"
    assert {
        path.relative_to(bootstrapped.workspace_root).as_posix(): path.read_bytes()
        for path in bootstrapped.workspace_root.rglob("*")
        if path.is_file()
    } == before


def test_success_preserves_input_tree_and_does_not_read_adjacent_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrapped = bootstrap_m1_workspace(
        tmp_path,
        fixture_names=("strict-two.txt", "unsupported-type.md"),
    )
    selected = next(
        source
        for source in bootstrapped.registry["sources"]
        if source["current_relative_path"] == "strict-two.txt"
    )
    adjacent = (bootstrapped.input_root / "unsupported-type.md").resolve()
    input_before = {
        path.relative_to(bootstrapped.input_root).as_posix(): path.read_bytes()
        for path in bootstrapped.input_root.rglob("*")
        if path.is_file()
    }
    original_open = Path.open

    def guarded_open(path: Path, *args, **kwargs):
        if path.resolve() == adjacent:
            raise AssertionError("adjacent source must not be read")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    result = run_single_choice_parse(
        input_root=bootstrapped.input_root,
        workspace_root=bootstrapped.workspace_root,
        source_id=selected["source_id"],
        now=fixed_now,
        uuid_factory=UUIDSequence(1800),
    )

    assert result.status == "complete"
    monkeypatch.setattr(Path, "open", original_open)
    assert {
        path.relative_to(bootstrapped.input_root).as_posix(): path.read_bytes()
        for path in bootstrapped.input_root.rglob("*")
        if path.is_file()
    } == input_before
