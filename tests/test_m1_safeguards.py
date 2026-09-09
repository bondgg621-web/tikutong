from __future__ import annotations

from pathlib import Path
import shutil
import socket

from conftest import REPOSITORY_ROOT, SKILL_ROOT
from m1_helpers import UUIDSequence, fixed_now, tree_snapshot
from qbcore.cli import run_inventory


FIXTURE = REPOSITORY_ROOT / "tests" / "fixtures" / "m1-discovery" / "input"


def test_full_run_preserves_every_source_byte(tmp_path: Path, monkeypatch) -> None:
    input_root = tmp_path / "input"
    shutil.copytree(FIXTURE, input_root)
    before = tree_snapshot(input_root)
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network attempted")))
    run_inventory(input_root=input_root, workspace_root=tmp_path / "workspace", now=fixed_now, uuid_factory=UUIDSequence(1))
    assert tree_snapshot(input_root) == before


def test_runtime_has_no_network_or_process_execution_imports() -> None:
    runtime = SKILL_ROOT / "scripts"
    text = "\n".join(path.read_text(encoding="utf-8") for path in runtime.rglob("*.py"))
    forbidden = ("import requests", "import urllib", "import httpx", "import socket", "import subprocess")
    assert not any(token in text for token in forbidden)


def test_persistent_artifacts_do_not_copy_source_text_or_absolute_paths(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    secret_marker = "SYNTHETIC-CONTENT-MUST-NOT-ENTER-STATE"
    (input_root / "source.txt").write_text(secret_marker, encoding="utf-8")
    workspace = tmp_path / "workspace"
    run_inventory(input_root=input_root, workspace_root=workspace, now=fixed_now, uuid_factory=UUIDSequence(1))
    persisted = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in workspace.rglob("*") if path.is_file())
    assert secret_marker not in persisted
    assert str(input_root) not in persisted
