from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
from uuid import UUID

from qbcore.capabilities import _utc_z
from qbcore.workspace import Workspace
from qbcore.workspace_contracts import validate_workspace_document


class CheckpointError(RuntimeError):
    pass


def _hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise CheckpointError("checkpoint contains an unsafe relative path")
    return path


def _read_object(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckpointError("checkpoint JSON cannot be read") from exc
    if not isinstance(value, dict):
        raise CheckpointError("checkpoint JSON root must be an object")
    return value


def _latest_complete_run(workspace: Workspace) -> Path | None:
    candidates: list[tuple[str, str, Path]] = []
    for run_dir in workspace.root.joinpath("runs").iterdir():
        state_path = run_dir / "workspace-run.json"
        if not run_dir.is_dir() or not state_path.is_file():
            continue
        try:
            state = _read_object(state_path)
        except CheckpointError:
            continue
        if validate_workspace_document("workspace-run", state):
            continue
        if state["status"] == "complete":
            candidates.append((state["updated_at"], state["run_id"], run_dir))
    return max(candidates, default=("", "", None))[2]


def _control_files(workspace: Workspace) -> list[Path]:
    required = [workspace.root / "project.json", workspace.root / "registry" / "sources.json"]
    if not all(path.is_file() for path in required):
        raise CheckpointError("project and registry must exist before checkpointing")
    selected = list(required)
    latest_run = _latest_complete_run(workspace)
    if latest_run is not None:
        for name in ("preflight.json", "discovery.json", "issues.json", "workspace-run.json"):
            path = latest_run / name
            if path.is_file():
                selected.append(path)
    return selected


def _validate_checkpoint_dir(workspace: Workspace, checkpoint_dir: Path) -> dict:
    checkpoint_dir = workspace.policy.assert_write_target(checkpoint_dir)
    manifest = _read_object(checkpoint_dir / "checkpoint-manifest.json")
    if validate_workspace_document("checkpoint-manifest", manifest):
        raise CheckpointError("checkpoint manifest is invalid")
    expected = {item["relative_path"]: item for item in manifest["files"]}
    if len(expected) != len(manifest["files"]):
        raise CheckpointError("checkpoint manifest contains duplicate paths")
    actual = {path.relative_to(checkpoint_dir).as_posix() for path in checkpoint_dir.rglob("*") if path.is_file() and path.name != "checkpoint-manifest.json"}
    if actual != set(expected):
        raise CheckpointError("checkpoint file set does not match its manifest")
    for relative, item in expected.items():
        path = checkpoint_dir / _safe_relative(relative)
        if path.stat().st_size != item["size_bytes"] or _hash(path) != item["content_hash"]:
            raise CheckpointError("checkpoint file hash or size does not match")
    return manifest


def create_checkpoint(workspace: Workspace, *, reason: str, uuid_factory: Callable[[], UUID], now: Callable[[], datetime]) -> dict:
    checkpoint_id = str(uuid_factory())
    staging = workspace.policy.assert_write_target(workspace.root / "checkpoints" / f"{checkpoint_id}.staging")
    final = workspace.policy.assert_write_target(workspace.root / "checkpoints" / checkpoint_id)
    if staging.exists() or final.exists():
        raise CheckpointError("checkpoint identifier already exists")
    staging.mkdir(parents=False)
    files: list[dict] = []
    for source in _control_files(workspace):
        relative = source.relative_to(workspace.root)
        destination = workspace.policy.assert_write_target(staging / relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        files.append({"relative_path": relative.as_posix(), "content_hash": _hash(destination), "size_bytes": destination.stat().st_size})
    files.sort(key=lambda item: item["relative_path"])
    manifest = {"schema_version": "1.0", "checkpoint_id": checkpoint_id, "created_at": _utc_z(now()), "reason": reason, "files": files}
    if validate_workspace_document("checkpoint-manifest", manifest):
        raise CheckpointError("generated checkpoint manifest is invalid")
    workspace.write_json_atomic(staging / "checkpoint-manifest.json", manifest)
    _validate_checkpoint_dir(workspace, staging)
    try:
        os.replace(staging, final)
    except OSError as exc:
        raise CheckpointError("checkpoint publication failed") from exc
    return _validate_checkpoint_dir(workspace, final)


def validate_checkpoint(workspace: Workspace, checkpoint_dir: Path) -> dict:
    resolved = checkpoint_dir.resolve(strict=True)
    if resolved.parent != (workspace.root / "checkpoints").resolve(strict=True):
        raise CheckpointError("checkpoint directory is outside the checkpoint root")
    if resolved.name.endswith(".staging"):
        raise CheckpointError("incomplete checkpoint staging is not restorable")
    return _validate_checkpoint_dir(workspace, resolved)


def restore_latest_checkpoint(workspace: Workspace, *, run_id: str, now: Callable[[], datetime]) -> list[str]:
    valid: list[tuple[str, str, Path, dict]] = []
    for candidate in (workspace.root / "checkpoints").iterdir():
        if not candidate.is_dir() or candidate.name.endswith(".staging"):
            continue
        try:
            manifest = validate_checkpoint(workspace, candidate)
        except CheckpointError:
            continue
        valid.append((manifest["created_at"], manifest["checkpoint_id"], candidate, manifest))
    if not valid:
        raise CheckpointError("no complete checkpoint is available")
    _, _, checkpoint_dir, manifest = max(valid)
    by_path = {item["relative_path"]: item for item in manifest["files"]}
    required = {"project.json", "registry/sources.json"}
    if not required <= set(by_path):
        raise CheckpointError("checkpoint lacks authoritative project or registry state")
    staging = workspace.policy.assert_write_target(workspace.root / "checkpoints" / f".restore-{run_id}.staging")
    if staging.exists():
        raise CheckpointError("restore staging already exists")
    staging.mkdir()
    try:
        for relative in sorted(required):
            source = checkpoint_dir / _safe_relative(relative)
            destination = workspace.policy.assert_write_target(staging / _safe_relative(relative))
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            expected = by_path[relative]
            if destination.stat().st_size != expected["size_bytes"] or _hash(destination) != expected["content_hash"]:
                raise CheckpointError("restore staging verification failed")
        workspace.write_project(_read_object(staging / "project.json"))
        workspace.write_registry(_read_object(staging / "registry" / "sources.json"))
        stamp = _utc_z(now())
        run = {"schema_version": "1.0", "run_id": run_id, "phase": "complete", "status": "complete", "started_at": stamp, "updated_at": stamp, "input_root_fingerprint": workspace.policy.input_fingerprint, "workspace_root_fingerprint": workspace.policy.workspace_fingerprint, "artifacts": [{"kind": "registry", "relative_path": "registry/sources.json", "content_hash": _hash(workspace.root / "registry" / "sources.json")}]} 
        workspace.write_run_artifact(run_id, "workspace-run.json", run)
    except (OSError, ValueError) as exc:
        raise CheckpointError("checkpoint restore failed") from exc
    try:
        shutil.rmtree(staging)
    except OSError:
        pass
    return sorted(required)
