from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from conftest import REPOSITORY_ROOT
from m1_helpers import UUIDSequence, fixed_now, tree_snapshot
from qbcore.cli import main, run_inventory


FIXTURE = REPOSITORY_ROOT / "tests" / "fixtures" / "m1-discovery" / "input"


def test_run_inventory_publishes_complete_workspace_without_touching_input(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    shutil.copytree(FIXTURE, input_root)
    workspace_root = input_root / ".workspace"
    before = tree_snapshot(input_root)
    result = run_inventory(input_root=input_root, workspace_root=workspace_root, now=fixed_now, uuid_factory=UUIDSequence(1))
    after_without_workspace = {path: digest for path, digest in tree_snapshot(input_root).items() if not path.startswith(".workspace/")}
    assert before == after_without_workspace
    assert result.status == "complete"
    assert (workspace_root / "project.json").is_file()
    assert (workspace_root / "registry" / "sources.json").is_file()
    run_dir = workspace_root / "runs" / result.run_id
    assert {path.name for path in run_dir.iterdir()} == {"discovery.json", "issues.json", "preflight.json", "workspace-run.json"}
    run = json.loads((run_dir / "workspace-run.json").read_text(encoding="utf-8"))
    assert run["phase"] == "complete"
    assert run["status"] == "complete"


def test_cli_requires_explicit_workspace_root(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    with pytest.raises(SystemExit) as raised:
        main(["inventory", "--input-root", str(input_root)])
    assert raised.value.code == 2
    assert list(input_root.iterdir()) == []


def test_cli_rejects_equal_roots_without_adding_input_files(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    assert main(["inventory", "--input-root", str(input_root), "--workspace-root", str(input_root)]) == 2
    assert list(input_root.iterdir()) == []


def test_cli_rejects_input_inside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    input_root = workspace / "input"
    input_root.mkdir(parents=True)
    assert main(["inventory", "--input-root", str(input_root), "--workspace-root", str(workspace)]) == 2


def test_second_unchanged_run_preserves_ids_but_still_hashes_every_file(tmp_path: Path, monkeypatch) -> None:
    input_root = tmp_path / "input"
    shutil.copytree(FIXTURE, input_root)
    workspace = tmp_path / "workspace"
    run_inventory(input_root=input_root, workspace_root=workspace, now=fixed_now, uuid_factory=UUIDSequence(1))
    before = json.loads((workspace / "registry" / "sources.json").read_text(encoding="utf-8"))
    import qbcore.discovery as discovery_module
    original = discovery_module._hash_file
    calls: list[str] = []

    def counting_hash(path: Path, chunk_size: int = 1024 * 1024) -> str:
        calls.append(path.name)
        return original(path, chunk_size)

    monkeypatch.setattr(discovery_module, "_hash_file", counting_hash)
    run_inventory(input_root=input_root, workspace_root=workspace, now=fixed_now, uuid_factory=UUIDSequence(100))
    after = json.loads((workspace / "registry" / "sources.json").read_text(encoding="utf-8"))
    assert after == before
    assert len(calls) == 4


def test_changed_second_run_checkpoints_previous_registry(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    source = input_root / "source.txt"
    source.write_text("version one\n", encoding="utf-8")
    workspace = tmp_path / "workspace"
    run_inventory(input_root=input_root, workspace_root=workspace, now=fixed_now, uuid_factory=UUIDSequence(1))
    source.write_text("version two\n", encoding="utf-8")
    run_inventory(input_root=input_root, workspace_root=workspace, now=fixed_now, uuid_factory=UUIDSequence(100))
    registry = json.loads((workspace / "registry" / "sources.json").read_text(encoding="utf-8"))
    assert registry["registry_revision"] == 2
    assert len([path for path in (workspace / "checkpoints").iterdir() if not path.name.endswith(".staging")]) == 1


def test_ambiguous_rename_is_published_as_an_open_issue(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    old = input_root / "old.txt"
    old.write_text("same bytes\n", encoding="utf-8")
    workspace = tmp_path / "workspace"
    run_inventory(input_root=input_root, workspace_root=workspace, now=fixed_now, uuid_factory=UUIDSequence(1))
    old.unlink()
    (input_root / "one.txt").write_text("same bytes\n", encoding="utf-8")
    (input_root / "two.txt").write_text("same bytes\n", encoding="utf-8")
    result = run_inventory(input_root=input_root, workspace_root=workspace, now=fixed_now, uuid_factory=UUIDSequence(100))
    issues = json.loads((workspace / "runs" / result.run_id / "issues.json").read_text(encoding="utf-8"))
    identity = [issue for issue in issues["issues"] if issue["code"] == "QB-IDENTITY-AMBIGUOUS"]
    assert len(identity) == 1 and identity[0]["status"] == "open"


def test_restore_without_checkpoint_fails_and_preserves_registry(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    (input_root / "source.txt").write_text("synthetic\n", encoding="utf-8")
    workspace = tmp_path / "workspace"
    run_inventory(input_root=input_root, workspace_root=workspace, now=fixed_now, uuid_factory=UUIDSequence(1))
    registry = workspace / "registry" / "sources.json"
    before = registry.read_bytes()
    assert main(["restore", "--input-root", str(input_root), "--workspace-root", str(workspace)]) == 2
    assert registry.read_bytes() == before
