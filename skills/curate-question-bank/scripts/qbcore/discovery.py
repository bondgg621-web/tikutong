from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from hashlib import sha256
import os
from pathlib import Path

from qbcore.capabilities import _utc_z
from qbcore.paths import RootPolicy, is_reparse_directory


BUILTIN_TEXT_SUFFIXES = {".txt", ".md"}


class DiscoveryError(RuntimeError):
    pass


def _hash_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def discover_files(policy: RootPolicy, *, now: Callable[[], datetime]) -> dict:
    entries: list[dict] = []
    skipped: list[dict] = []
    issues: list[dict] = []
    pending = [policy.input_root]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as iterator:
                children = sorted(iterator, key=lambda item: (item.name.casefold(), item.name))
        except OSError as exc:
            if directory == policy.input_root:
                raise DiscoveryError("input_root cannot be enumerated") from exc
            relative_directory = directory.relative_to(policy.input_root).as_posix()
            issues.append({"code": "QB-SOURCE-READ-FAILED", "relative_path": relative_directory, "summary": "authorized source directory could not be read"})
            continue
        for child in children:
            path = Path(child.path)
            resolved = path.resolve(strict=False)
            if policy.contains_workspace(resolved):
                continue
            relative = path.relative_to(policy.input_root).as_posix()
            if child.is_dir(follow_symlinks=False):
                if is_reparse_directory(path):
                    skipped.append({"relative_path": relative, "reason": "reparse_point"})
                else:
                    pending.append(path)
                continue
            if child.is_symlink() or is_reparse_directory(path) or not child.is_file(follow_symlinks=False):
                skipped.append({"relative_path": relative, "reason": "reparse_point"})
                continue
            try:
                content_hash = _hash_file(path)
                size_bytes = path.stat().st_size
            except OSError:
                entries.append({"relative_path": relative, "size_bytes": None, "content_hash": None, "support_status": "read_failed"})
                issues.append({"code": "QB-SOURCE-READ-FAILED", "relative_path": relative, "summary": "authorized source could not be read"})
                continue
            supported = path.suffix.casefold() in BUILTIN_TEXT_SUFFIXES
            entries.append({"relative_path": relative, "size_bytes": size_bytes, "content_hash": content_hash, "support_status": "builtin_text" if supported else "unsupported"})
            if not supported:
                issues.append({"code": "QB-SOURCE-UNSUPPORTED", "relative_path": relative, "summary": "source format is not supported in Milestone 1"})
    entries.sort(key=lambda item: (item["relative_path"].casefold(), item["relative_path"]))
    skipped.sort(key=lambda item: (item["relative_path"].casefold(), item["relative_path"]))
    issues.sort(key=lambda item: (item["relative_path"].casefold(), item["code"]))
    return {
        "schema_version": "1.0",
        "generated_at": _utc_z(now()),
        "input_root_fingerprint": policy.input_fingerprint,
        "workspace_root_fingerprint": policy.workspace_fingerprint,
        "entries": entries,
        "skipped_directories": skipped,
        "issues": issues,
    }
