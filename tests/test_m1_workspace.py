from __future__ import annotations

import json
from pathlib import Path

import pytest

from qbcore.paths import PathPolicyError, validate_roots
from qbcore.workspace import Workspace, WorkspaceWriteError


def test_initialize_creates_only_the_frozen_workspace_layout(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    policy = validate_roots(input_root, tmp_path / "workspace")
    workspace = Workspace.initialize(policy)
    assert sorted(path.name for path in policy.workspace_root.iterdir()) == ["checkpoints", "logs", "outputs", "registry", "runs"]
    assert workspace.root == policy.workspace_root


def test_write_json_rejects_targets_outside_workspace(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    workspace = Workspace.initialize(validate_roots(input_root, tmp_path / "workspace"))
    with pytest.raises(PathPolicyError, match="escapes workspace_root"):
        workspace.write_json_atomic(tmp_path / "outside.json", {"value": 1})


def test_failed_replace_preserves_previous_complete_json(tmp_path: Path, monkeypatch) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    workspace = Workspace.initialize(validate_roots(input_root, tmp_path / "workspace"))
    target = workspace.root / "registry" / "sources.json"
    workspace.write_json_atomic(target, {"version": 1})
    monkeypatch.setattr("qbcore.workspace.os.replace", lambda *_: (_ for _ in ()).throw(OSError("injected")))
    with pytest.raises(WorkspaceWriteError, match="atomic JSON publication failed"):
        workspace.write_json_atomic(target, {"version": 2})
    assert json.loads(target.read_text(encoding="utf-8")) == {"version": 1}


def test_atomic_json_bytes_are_independent_of_mapping_insertion_order(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    workspace = Workspace.initialize(validate_roots(input_root, tmp_path / "workspace"))
    target = workspace.root / "runs" / "freeform-test.json"
    workspace.write_json_atomic(target, {"z": 1, "a": 2})
    first = target.read_bytes()
    workspace.write_json_atomic(target, {"a": 2, "z": 1})
    assert target.read_bytes() == first


def test_invalid_project_is_rejected_before_target_creation(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    workspace = Workspace.initialize(validate_roots(input_root, tmp_path / "workspace"))
    target = workspace.root / "project.json"
    with pytest.raises(WorkspaceWriteError, match="invalid workspace-project"):
        workspace.write_project({"schema_version": "1.0"})
    assert not target.exists()


def test_injected_replace_failure_leaves_no_temporary_file(tmp_path: Path, monkeypatch) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    workspace = Workspace.initialize(validate_roots(input_root, tmp_path / "workspace"))
    target = workspace.root / "registry" / "freeform.json"
    monkeypatch.setattr("qbcore.workspace.os.replace", lambda *_: (_ for _ in ()).throw(OSError("injected")))
    with pytest.raises(WorkspaceWriteError):
        workspace.write_json_atomic(target, {"value": 1})
    assert not target.exists()
    assert list(target.parent.glob("*.tmp")) == []
    assert all(path.resolve().is_relative_to(workspace.root.resolve()) for path in workspace.root.rglob("*"))
