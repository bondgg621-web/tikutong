from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path


class PathPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class RootPolicy:
    input_root: Path
    workspace_root: Path
    workspace_is_inside_input: bool

    @property
    def input_fingerprint(self) -> str:
        return _fingerprint(self.input_root)

    @property
    def workspace_fingerprint(self) -> str:
        return _fingerprint(self.workspace_root)

    def contains_input(self, path: Path) -> bool:
        return _is_within(path.resolve(strict=False), self.input_root)

    def contains_workspace(self, path: Path) -> bool:
        return _is_within(path.resolve(strict=False), self.workspace_root)

    def assert_write_target(self, path: Path) -> Path:
        resolved = path.resolve(strict=False)
        if not _is_within(resolved, self.workspace_root):
            raise PathPolicyError("write target escapes workspace_root")
        _reject_reparse_ancestors(self.workspace_root, resolved.parent)
        return resolved


def _fingerprint(path: Path) -> str:
    normalized = os.path.normcase(str(path.resolve(strict=False)))
    return sha256(normalized.encode("utf-8")).hexdigest()


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def is_reparse_directory(path: Path) -> bool:
    return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())


def _reject_reparse_ancestors(root: Path, parent: Path) -> None:
    current = parent
    checked: list[Path] = []
    while _is_within(current, root) and current != root:
        checked.append(current)
        current = current.parent
    for candidate in reversed(checked):
        if candidate.exists() and is_reparse_directory(candidate):
            raise PathPolicyError("write target crosses a reparse point")


def validate_roots(input_root: str | Path | None, workspace_root: str | Path | None) -> RootPolicy:
    if input_root is None or str(input_root).strip() == "":
        raise PathPolicyError("input_root is required")
    if workspace_root is None or str(workspace_root).strip() == "":
        raise PathPolicyError("workspace_root is required")
    try:
        input_path = Path(input_root).expanduser().resolve(strict=True)
        workspace_path = Path(workspace_root).expanduser().resolve(strict=False)
    except (FileNotFoundError, OSError, RuntimeError) as exc:
        raise PathPolicyError("root paths cannot be safely resolved") from exc
    if not input_path.is_dir():
        raise PathPolicyError("input_root must be an existing directory")
    if input_path == workspace_path:
        raise PathPolicyError("input_root and workspace_root must be different")
    if _is_within(input_path, workspace_path):
        raise PathPolicyError("input_root cannot be inside workspace_root")
    return RootPolicy(
        input_root=input_path,
        workspace_root=workspace_path,
        workspace_is_inside_input=_is_within(workspace_path, input_path),
    )
