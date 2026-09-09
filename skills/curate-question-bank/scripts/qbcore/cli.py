from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from uuid import UUID, uuid4

from qbcore.capabilities import _utc_z, build_capability_matrix
from qbcore.discovery import discover_files
from qbcore.paths import RootPolicy, validate_roots
from qbcore.parse_service import (
    ParsePublicationError,
    ParseServiceError,
    SourceResolutionError,
    run_single_choice_parse,
)
from qbcore.recovery import create_checkpoint, restore_latest_checkpoint
from qbcore.registry import reconcile_registry
from qbcore.workspace import Workspace, WorkspaceWriteError
from qbcore.workspace_contracts import validate_workspace_document


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: str
    workspace_root: Path


def system_now() -> datetime:
    return datetime.now(timezone.utc)


def system_uuid() -> UUID:
    return uuid4()


def _new_project(*, dataset_id: str, now: Callable[[], datetime]) -> dict:
    return {"schema_version": "1.0", "project_format_version": "1.0", "dataset_id": dataset_id, "created_at": _utc_z(now())}


def _empty_registry(*, dataset_id: str, now: Callable[[], datetime]) -> dict:
    return {"schema_version": "1.0", "dataset_id": dataset_id, "registry_revision": 0, "updated_at": _utc_z(now()), "sources": []}


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise WorkspaceWriteError("workspace JSON root must be an object")
    return value


def _require_document(kind: str, value: dict) -> None:
    issues = validate_workspace_document(kind, value)
    if issues:
        first = issues[0]
        raise WorkspaceWriteError(f"invalid {kind} at {first.path}: {first.message}")


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _build_workspace_issues(*, run_id: str, discovery_issues: list[dict], identity_issues: list[dict], uuid_factory: Callable[[], UUID]) -> dict:
    rows: list[dict] = []
    for issue in discovery_issues:
        rows.append({"issue_id": str(uuid_factory()), "code": issue["code"], "status": "open", "summary": issue["summary"], "relative_paths": [issue["relative_path"]], "source_ids": []})
    for issue in identity_issues:
        rows.append({"issue_id": str(uuid_factory()), "code": issue["code"], "status": "open", "summary": issue["summary"], "relative_paths": issue["relative_paths"], "source_ids": issue["source_ids"]})
    rows.sort(key=lambda item: (item["code"], item["relative_paths"], item["issue_id"]))
    return {"schema_version": "1.0", "run_id": run_id, "issues": rows}


def _complete_run_document(*, run_id: str, started_at: str, policy: RootPolicy, now: Callable[[], datetime], workspace: Workspace) -> dict:
    paths = (("preflight", workspace.root / "runs" / run_id / "preflight.json"), ("discovery", workspace.root / "runs" / run_id / "discovery.json"), ("issues", workspace.root / "runs" / run_id / "issues.json"), ("registry", workspace.root / "registry" / "sources.json"))
    artifacts = [{"kind": kind, "relative_path": path.relative_to(workspace.root).as_posix(), "content_hash": _hash_file(path)} for kind, path in paths]
    return {"schema_version": "1.0", "run_id": run_id, "phase": "complete", "status": "complete", "started_at": started_at, "updated_at": _utc_z(now()), "input_root_fingerprint": policy.input_fingerprint, "workspace_root_fingerprint": policy.workspace_fingerprint, "artifacts": artifacts}


def _append_event_log(workspace: Workspace, run_id: str, event: str, summary: str, *, now: Callable[[], datetime]) -> None:
    target = workspace.policy.assert_write_target(workspace.root / "logs" / "events.jsonl")
    record = {"timestamp": _utc_z(now()), "run_id": run_id, "event": event, "summary": summary}
    payload = (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    with target.open("ab") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def run_inventory(*, input_root: str | Path, workspace_root: str | Path, now: Callable[[], datetime] = system_now, uuid_factory: Callable[[], UUID] = system_uuid) -> RunResult:
    policy = validate_roots(input_root, workspace_root)
    workspace = Workspace.initialize(policy)
    run_id = str(uuid_factory())
    started_at = _utc_z(now())
    phase = "preflight"
    project_path = workspace.root / "project.json"
    registry_path = workspace.root / "registry" / "sources.json"
    try:
        if project_path.exists():
            project = _load_json(project_path)
            _require_document("workspace-project", project)
        else:
            project = _new_project(dataset_id=str(uuid_factory()), now=now)
            workspace.write_project(project)
        previous_registry = _load_json(registry_path) if registry_path.exists() else _empty_registry(dataset_id=project["dataset_id"], now=now)
        _require_document("source-registry", previous_registry)
        if previous_registry["dataset_id"] != project["dataset_id"]:
            raise WorkspaceWriteError("project and registry dataset IDs differ")
        preflight = build_capability_matrix(policy, now=now, skill_version="0.1.0")
        _require_document("capability-matrix", preflight)
        phase = "discovery"
        discovery = discover_files(policy, now=now)
        _require_document("discovery-inventory", discovery)
        phase = "registry"
        next_registry, identity_issues = reconcile_registry(previous_registry, discovery, uuid_factory=uuid_factory, now=now)
        _require_document("source-registry", next_registry)
        issue_rows = _build_workspace_issues(run_id=run_id, discovery_issues=discovery["issues"], identity_issues=identity_issues, uuid_factory=uuid_factory)
        _require_document("workspace-issues", issue_rows)
        if registry_path.exists() and next_registry != previous_registry:
            phase = "checkpoint"
            create_checkpoint(workspace, reason="registry_update", uuid_factory=uuid_factory, now=now)
        workspace.write_run_artifact(run_id, "preflight.json", preflight)
        workspace.write_run_artifact(run_id, "discovery.json", discovery)
        workspace.write_run_artifact(run_id, "issues.json", issue_rows)
        if next_registry != previous_registry or not registry_path.exists():
            workspace.write_registry(next_registry)
        _append_event_log(workspace, run_id, "publication_ready", "validated inventory artifacts published", now=now)
        complete_run = _complete_run_document(run_id=run_id, started_at=started_at, policy=policy, now=now, workspace=workspace)
        _require_document("workspace-run", complete_run)
        workspace.write_run_artifact(run_id, "workspace-run.json", complete_run)
        return RunResult(run_id=run_id, status="complete", workspace_root=workspace.root)
    except Exception:
        failed = {"schema_version": "1.0", "run_id": run_id, "phase": phase, "status": "failed", "started_at": started_at, "updated_at": _utc_z(now()), "input_root_fingerprint": policy.input_fingerprint, "workspace_root_fingerprint": policy.workspace_fingerprint, "artifacts": []}
        try:
            workspace.write_run_artifact(run_id, "workspace-run.json", failed)
        except Exception:
            pass
        raise


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        self.exit(2, "error: invalid arguments\n")


def build_parser() -> argparse.ArgumentParser:
    parser = _SanitizedArgumentParser(prog="curate-question-bank")
    subparsers = parser.add_subparsers(dest="command", required=True)
    inventory = subparsers.add_parser("inventory")
    inventory.add_argument("--input-root", required=True)
    inventory.add_argument("--workspace-root", required=True)
    restore = subparsers.add_parser("restore")
    restore.add_argument("--input-root", required=True)
    restore.add_argument("--workspace-root", required=True)
    parse_single_choice = subparsers.add_parser("parse-single-choice")
    parse_single_choice.add_argument("--input-root", required=True)
    parse_single_choice.add_argument("--workspace-root", required=True)
    parse_single_choice.add_argument("--source-id", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    exit_code = 0
    try:
        if args.command == "inventory":
            result = run_inventory(input_root=args.input_root, workspace_root=args.workspace_root)
        elif args.command == "restore":
            policy = validate_roots(args.input_root, args.workspace_root)
            workspace = Workspace.initialize(policy)
            run_id = str(system_uuid())
            restore_latest_checkpoint(workspace, run_id=run_id, now=system_now)
            result = RunResult(run_id, "complete", workspace.root)
        else:
            result = run_single_choice_parse(
                input_root=args.input_root,
                workspace_root=args.workspace_root,
                source_id=args.source_id,
                now=system_now,
                uuid_factory=system_uuid,
            )
            if result.status == "needs_review":
                exit_code = 3
    except (SourceResolutionError, ParseServiceError, ParsePublicationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception:
        print("error: operation failed", file=sys.stderr)
        return 2
    print(json.dumps({"run_id": result.run_id, "status": result.status}, sort_keys=True))
    return exit_code
