from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import UUID


FIXED_TIME = datetime(2026, 8, 13, 0, 0, tzinfo=timezone.utc)


class UUIDSequence:
    def __init__(self, start: int = 1) -> None:
        self._next = start

    def __call__(self) -> UUID:
        value = UUID(int=self._next, version=4)
        self._next += 1
        return value


def fixed_now() -> datetime:
    return FIXED_TIME


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def tree_snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): file_hash(path)
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold())
        if path.is_file()
    }
