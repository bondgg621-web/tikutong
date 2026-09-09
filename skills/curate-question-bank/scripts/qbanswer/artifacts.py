"""Strict JSON, hashing, and workspace-confined file primitives for M3."""
from __future__ import annotations

from hashlib import sha256
import json
import math
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from qbcore.paths import RootPolicy

ABSENT = "ABSENT"

class ArtifactError(RuntimeError):
    pass


def _exact_json(value: Any, path: str = "$") -> None:
    t = type(value)
    if t in (str, int, bool) or value is None:
        return
    if t is float:
        if not math.isfinite(value):
            raise ArtifactError(f"non-finite JSON number at {path}")
        return
    if t is list:
        for i, item in enumerate(value):
            _exact_json(item, f"{path}[{i}]")
        return
    if t is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ArtifactError(f"non-string JSON key at {path}")
            _exact_json(item, f"{path}.{key}")
        return
    raise ArtifactError(f"non-exact JSON type at {path}")


def compact_json_bytes(value: Any) -> bytes:
    _exact_json(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def workspace_json_bytes(value: Any) -> bytes:
    _exact_json(value)
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def digest_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def digest_value(value: Any) -> str:
    return digest_bytes(workspace_json_bytes(value))


def read_json_bytes(path: Path) -> tuple[dict, bytes, str]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ArtifactError("artifact could not be read") from exc
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ArtifactError("artifact JSON must not contain BOM")
    try:
        text=raw.decode("utf-8", errors="strict")
        value=json.loads(text)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactError("artifact JSON is invalid") from exc
    if type(value) is not dict:
        raise ArtifactError("artifact JSON root must be an object")
    _exact_json(value)
    if workspace_json_bytes(value) != raw:
        raise ArtifactError("artifact JSON bytes are not canonical")
    return value, raw, digest_bytes(raw)


def safe_relative(relative: str) -> str:
    if type(relative) is not str or not relative or "\\" in relative:
        raise ArtifactError("artifact relative path is invalid")
    pure=Path(relative)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        raise ArtifactError("artifact relative path is invalid")
    return pure.as_posix()


def resolve_workspace(policy: RootPolicy, relative: str) -> Path:
    relative=safe_relative(relative)
    return policy.assert_write_target(policy.workspace_root / relative)


def _fsync_parent(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        fd=os.open(path.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_atomic_json(policy: RootPolicy, relative: str, value: dict) -> tuple[str,str]:
    target=resolve_workspace(policy, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload=workspace_json_bytes(value)
    temp=policy.assert_write_target(target.parent/f".{target.name}.{uuid4()}.tmp")
    try:
        with temp.open("xb") as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        if temp.read_bytes()!=payload:
            raise ArtifactError("atomic JSON temporary read-back failed")
        os.replace(temp,target)
        _fsync_parent(target)
        if target.read_bytes()!=payload:
            raise ArtifactError("atomic JSON replace read-back failed")
    except Exception as exc:
        try: temp.unlink(missing_ok=True)
        except OSError: pass
        if isinstance(exc, ArtifactError): raise
        raise ArtifactError("atomic JSON publication failed") from exc
    return relative,digest_bytes(payload)


def write_immutable_json(policy: RootPolicy, relative: str, value: dict) -> tuple[str,str]:
    target=resolve_workspace(policy, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload=workspace_json_bytes(value)
    if target.exists():
        try: existing=target.read_bytes()
        except OSError as exc: raise ArtifactError("immutable artifact could not be read") from exc
        if existing != payload:
            raise ArtifactError("immutable artifact already exists with different bytes")
        return relative,digest_bytes(existing)
    # Portable no-overwrite publication: reserve target with exclusive create, write exact bytes once.
    # This avoids POSIX-only hard-link assumptions and is valid on Windows/POSIX.
    try:
        with target.open("xb") as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        _fsync_parent(target)
        if target.read_bytes()!=payload:
            raise ArtifactError("immutable artifact read-back failed")
    except FileExistsError:
        return write_immutable_json(policy,relative,value)
    except Exception as exc:
        if isinstance(exc,ArtifactError): raise
        raise ArtifactError("immutable artifact publication failed") from exc
    return relative,digest_bytes(payload)


def read_relative(policy: RootPolicy, relative: str) -> tuple[dict,bytes,str]:
    path=resolve_workspace(policy,relative)
    return read_json_bytes(path)


def current_pointer(policy: RootPolicy) -> tuple[str,dict|None]:
    path=policy.assert_write_target(policy.workspace_root/'state/answer-association/current.json')
    if not path.exists(): return ABSENT,None
    value,raw,digest=read_json_bytes(path)
    return digest,value
