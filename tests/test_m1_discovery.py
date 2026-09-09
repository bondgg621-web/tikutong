from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import shutil

from conftest import REPOSITORY_ROOT
from m1_helpers import fixed_now, tree_snapshot
from qbcore.discovery import discover_files
from qbcore.paths import validate_roots
from qbcore.workspace_contracts import validate_workspace_document


FIXTURE = REPOSITORY_ROOT / "tests" / "fixtures" / "m1-discovery" / "input"


def test_discovery_is_deterministic_and_does_not_modify_input(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    shutil.copytree(FIXTURE, input_root)
    workspace = input_root / ".workspace"
    workspace.mkdir()
    (workspace / "must-not-scan.txt").write_text("workspace output\n", encoding="utf-8")
    before = tree_snapshot(input_root)
    policy = validate_roots(input_root, workspace)
    result = discover_files(policy, now=fixed_now)
    after = tree_snapshot(input_root)
    assert before == after
    assert [entry["relative_path"] for entry in result["entries"]] == [
        "alpha.txt", "beta.md", "nested/gamma.TXT", "unsupported.pdf"
    ]
    assert all(not item["relative_path"].startswith(".workspace/") for item in result["entries"])
    entry_by_path = {entry["relative_path"]: entry for entry in result["entries"]}
    assert entry_by_path["alpha.txt"]["support_status"] == "builtin_text"
    assert entry_by_path["nested/gamma.TXT"]["support_status"] == "builtin_text"
    assert entry_by_path["unsupported.pdf"]["support_status"] == "unsupported"
    assert entry_by_path["alpha.txt"]["content_hash"] == sha256(b"Synthetic alpha source.\n").hexdigest()
    assert {issue["code"] for issue in result["issues"]} == {"QB-SOURCE-UNSUPPORTED"}
    assert validate_workspace_document("discovery-inventory", result) == []


def test_empty_input_returns_empty_inventory(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    policy = validate_roots(input_root, tmp_path / "workspace")
    result = discover_files(policy, now=fixed_now)
    assert result["entries"] == []
    assert result["issues"] == []


def test_reversed_filesystem_enumeration_produces_the_same_inventory(tmp_path: Path, monkeypatch) -> None:
    input_root = tmp_path / "input"
    shutil.copytree(FIXTURE, input_root)
    policy = validate_roots(input_root, tmp_path / "workspace")
    normal = discover_files(policy, now=fixed_now)
    original = __import__("os").scandir

    class ReversedScandir:
        def __init__(self, path: Path) -> None:
            with original(path) as iterator:
                self.items = list(iterator)[::-1]

        def __enter__(self):
            return iter(self.items)

        def __exit__(self, *_args) -> None:
            return None

    monkeypatch.setattr("qbcore.discovery.os.scandir", ReversedScandir)
    assert discover_files(policy, now=fixed_now) == normal


def test_unreadable_file_is_recorded_without_a_fake_hash(tmp_path: Path, monkeypatch) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    (input_root / "blocked.txt").write_text("synthetic\n", encoding="utf-8")
    policy = validate_roots(input_root, tmp_path / "workspace")
    monkeypatch.setattr("qbcore.discovery._hash_file", lambda path: (_ for _ in ()).throw(PermissionError("injected")))
    result = discover_files(policy, now=fixed_now)
    assert result["entries"] == [{"relative_path": "blocked.txt", "size_bytes": None, "content_hash": None, "support_status": "read_failed"}]
    assert [issue["code"] for issue in result["issues"]] == ["QB-SOURCE-READ-FAILED"]


def test_workspace_and_alias_to_workspace_are_not_discovered(tmp_path: Path, monkeypatch) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    workspace = input_root / ".workspace"
    workspace.mkdir()
    (workspace / "output.txt").write_text("must not scan\n", encoding="utf-8")
    alias = input_root / "workspace-alias"
    try:
        alias.symlink_to(workspace, target_is_directory=True)
    except OSError:
        alias.mkdir()
        (alias / "also-output.txt").write_text("must not scan\n", encoding="utf-8")
        original = __import__("qbcore.discovery", fromlist=["is_reparse_directory"]).is_reparse_directory
        monkeypatch.setattr("qbcore.discovery.is_reparse_directory", lambda path: True if path == alias else original(path))
    policy = validate_roots(input_root, workspace)
    result = discover_files(policy, now=fixed_now)
    assert result["entries"] == []
