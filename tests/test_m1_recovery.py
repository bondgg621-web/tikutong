from __future__ import annotations

import json
from pathlib import Path

import pytest

from m1_helpers import UUIDSequence, fixed_now, tree_snapshot
from qbcore.paths import validate_roots
from qbcore.recovery import CheckpointError, create_checkpoint, restore_latest_checkpoint, validate_checkpoint
from qbcore.workspace import Workspace


def prepared_workspace(tmp_path: Path) -> tuple[Path, Workspace, dict, dict]:
    input_root = tmp_path / "input"
    input_root.mkdir()
    (input_root / "source.txt").write_text("synthetic input\n", encoding="utf-8")
    workspace = Workspace.initialize(validate_roots(input_root, tmp_path / "workspace"))
    project = {"schema_version": "1.0", "project_format_version": "1.0", "dataset_id": "00000000-0000-4000-8000-000000000100", "created_at": "2026-08-13T00:00:00Z"}
    registry = {"schema_version": "1.0", "dataset_id": project["dataset_id"], "registry_revision": 0, "updated_at": "2026-08-13T00:00:00Z", "sources": []}
    workspace.write_project(project)
    workspace.write_registry(registry)
    return input_root, workspace, project, registry


def only_complete_checkpoint(workspace: Workspace) -> Path:
    return next(path for path in (workspace.root / "checkpoints").iterdir() if path.is_dir() and not path.name.endswith(".staging"))


def make_checkpoint(workspace: Workspace) -> Path:
    create_checkpoint(workspace, reason="registry_update", uuid_factory=UUIDSequence(1), now=fixed_now)
    return only_complete_checkpoint(workspace)


def test_checkpoint_contains_only_complete_control_state(tmp_path: Path) -> None:
    input_root, workspace, _, _ = prepared_workspace(tmp_path)
    (input_root / "source.txt").write_text("do not copy\n", encoding="utf-8")
    checkpoint = create_checkpoint(workspace, reason="registry_update", uuid_factory=UUIDSequence(1), now=fixed_now)
    files = {item["relative_path"] for item in checkpoint["files"]}
    assert files == {"project.json", "registry/sources.json"}
    assert not any(path.name == "source.txt" for path in workspace.root.rglob("*"))


def test_checkpoint_missing_listed_file_is_rejected(tmp_path: Path) -> None:
    _, workspace, _, _ = prepared_workspace(tmp_path)
    checkpoint = make_checkpoint(workspace)
    (checkpoint / "project.json").unlink()
    with pytest.raises(CheckpointError, match="file set"):
        validate_checkpoint(workspace, checkpoint)


def test_checkpoint_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    _, workspace, _, _ = prepared_workspace(tmp_path)
    checkpoint = make_checkpoint(workspace)
    (checkpoint / "project.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(CheckpointError, match="hash or size"):
        validate_checkpoint(workspace, checkpoint)


def test_checkpoint_extra_unlisted_file_is_rejected(tmp_path: Path) -> None:
    _, workspace, _, _ = prepared_workspace(tmp_path)
    checkpoint = make_checkpoint(workspace)
    (checkpoint / "extra.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(CheckpointError, match="file set"):
        validate_checkpoint(workspace, checkpoint)


def test_restore_ignores_incomplete_staging_and_uses_complete_checkpoint(tmp_path: Path) -> None:
    _, workspace, _, registry = prepared_workspace(tmp_path)
    make_checkpoint(workspace)
    (workspace.root / "checkpoints" / "incomplete.staging").mkdir()
    changed = dict(registry, registry_revision=1, updated_at="2026-08-13T01:00:00Z")
    workspace.write_registry(changed)
    restored = restore_latest_checkpoint(workspace, run_id="00000000-0000-4000-8000-000000000200", now=fixed_now)
    assert restored == ["project.json", "registry/sources.json"]
    assert json.loads((workspace.root / "registry" / "sources.json").read_text(encoding="utf-8")) == registry


def test_all_invalid_checkpoints_fail_without_changing_current_registry(tmp_path: Path) -> None:
    _, workspace, _, _ = prepared_workspace(tmp_path)
    checkpoint = make_checkpoint(workspace)
    (checkpoint / "project.json").write_text("corrupt", encoding="utf-8")
    before = (workspace.root / "registry" / "sources.json").read_bytes()
    with pytest.raises(CheckpointError, match="no complete checkpoint"):
        restore_latest_checkpoint(workspace, run_id="00000000-0000-4000-8000-000000000200", now=fixed_now)
    assert (workspace.root / "registry" / "sources.json").read_bytes() == before


def test_valid_restore_preserves_input_bytes(tmp_path: Path) -> None:
    input_root, workspace, _, registry = prepared_workspace(tmp_path)
    before = tree_snapshot(input_root)
    make_checkpoint(workspace)
    workspace.write_registry(dict(registry, registry_revision=1, updated_at="2026-08-13T01:00:00Z"))
    restore_latest_checkpoint(workspace, run_id="00000000-0000-4000-8000-000000000200", now=fixed_now)
    assert tree_snapshot(input_root) == before
    assert json.loads((workspace.root / "registry" / "sources.json").read_text(encoding="utf-8")) == registry


def test_checkpoint_copy_failure_never_replaces_registry(tmp_path: Path, monkeypatch) -> None:
    _, workspace, _, _ = prepared_workspace(tmp_path)
    before = (workspace.root / "registry" / "sources.json").read_bytes()
    monkeypatch.setattr("qbcore.recovery.shutil.copyfile", lambda *_: (_ for _ in ()).throw(OSError("injected")))
    with pytest.raises(OSError, match="injected"):
        create_checkpoint(workspace, reason="registry_update", uuid_factory=UUIDSequence(1), now=fixed_now)
    assert (workspace.root / "registry" / "sources.json").read_bytes() == before
