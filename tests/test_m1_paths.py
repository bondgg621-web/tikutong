from __future__ import annotations

from pathlib import Path

import pytest

from qbcore.paths import PathPolicyError, is_reparse_directory, validate_roots


def test_roots_must_be_explicit() -> None:
    with pytest.raises(PathPolicyError, match="input_root is required"):
        validate_roots(None, "workspace")
    with pytest.raises(PathPolicyError, match="workspace_root is required"):
        validate_roots("input", None)


def test_equal_roots_are_rejected_before_workspace_creation(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    with pytest.raises(PathPolicyError, match="must be different"):
        validate_roots(input_root, input_root)
    assert list(input_root.iterdir()) == []


def test_input_inside_workspace_is_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    input_root = workspace / "input"
    input_root.mkdir(parents=True)
    with pytest.raises(PathPolicyError, match="input_root cannot be inside workspace_root"):
        validate_roots(input_root, workspace)


def test_workspace_inside_input_is_allowed(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    policy = validate_roots(input_root, input_root / ".curator-workspace")
    assert policy.workspace_is_inside_input is True
    assert policy.workspace_root == (input_root / ".curator-workspace").resolve()


def test_write_target_outside_workspace_is_rejected(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    policy = validate_roots(input_root, tmp_path / "workspace")
    with pytest.raises(PathPolicyError, match="escapes workspace_root"):
        policy.assert_write_target(tmp_path / "outside.json")


def test_path_fingerprints_do_not_expose_absolute_paths(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    policy = validate_roots(input_root, tmp_path / "workspace")
    assert len(policy.input_fingerprint) == 64
    assert str(tmp_path) not in policy.input_fingerprint


def test_reparse_helper_treats_directory_symlink_as_reparse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        original = Path.is_symlink
        monkeypatch.setattr(
            Path,
            "is_symlink",
            lambda self: True if self == link else original(self),
        )
    assert is_reparse_directory(link) is True
