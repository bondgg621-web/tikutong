from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unicodedata
from uuid import UUID

from conftest import REPOSITORY_ROOT, SCRIPTS_ROOT
from qbcore.cli import RunResult, run_inventory


M2_FIXTURE_ROOT = REPOSITORY_ROOT / "tests" / "fixtures" / "m2-parser"
FIXED_TIME = datetime(2026, 8, 14, 0, 0, tzinfo=timezone.utc)
UTF8_BOM_CRLF_BYTES = (
    b"\xef\xbb\xbf"
    b"1. [single_choice] Which line-ending fixture is synthetic?\r\n"
    b"   - A. CRLF\r\n"
    b"   - B. LF\r\n"
)


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


def write_exact_bytes(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def write_utf8_bom_crlf_fixture(path: Path) -> Path:
    return write_exact_bytes(path, UTF8_BOM_CRLF_BYTES)


def copy_m2_fixture(name: str, destination: Path) -> Path:
    source = M2_FIXTURE_ROOT / name
    if source.parent != M2_FIXTURE_ROOT or not source.is_file():
        raise ValueError(f"unknown canonical M2 fixture: {name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def copy_m2_fixture_tree(destination: Path) -> Path:
    if destination.exists():
        raise FileExistsError(f"fixture destination already exists: {destination}")
    shutil.copytree(M2_FIXTURE_ROOT, destination)
    return destination


def expected_normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def expected_canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def expected_text_fingerprint(value: str) -> str:
    return sha256(expected_normalize_text(value).encode("utf-8")).hexdigest()


def expected_option_set_fingerprint(option_texts: Iterable[str]) -> str:
    normalized = sorted(expected_normalize_text(value) for value in option_texts)
    return sha256(expected_canonical_json_bytes(normalized)).hexdigest()


def expected_content_revision_fingerprint(stem: str, option_texts: Iterable[str]) -> str:
    payload = {
        "options": [expected_normalize_text(value) for value in option_texts],
        "question_type": "single_choice",
        "stem": expected_normalize_text(stem),
    }
    return sha256(expected_canonical_json_bytes(payload)).hexdigest()


@dataclass(frozen=True)
class M1WorkspaceBootstrap:
    input_root: Path
    workspace_root: Path
    result: RunResult
    discovery: dict
    registry: dict


def bootstrap_m1_workspace(
    root: Path,
    *,
    fixture_names: Iterable[str] = ("strict-seven.md",),
    uuid_start: int = 1,
) -> M1WorkspaceBootstrap:
    input_root = root / "input"
    workspace_root = root / "workspace"
    input_root.mkdir(parents=True)
    for name in fixture_names:
        copy_m2_fixture(name, input_root / name)
    result = run_inventory(
        input_root=input_root,
        workspace_root=workspace_root,
        now=fixed_now,
        uuid_factory=UUIDSequence(uuid_start),
    )
    discovery = json.loads(
        (workspace_root / "runs" / result.run_id / "discovery.json").read_text(encoding="utf-8")
    )
    registry = json.loads(
        (workspace_root / "registry" / "sources.json").read_text(encoding="utf-8")
    )
    return M1WorkspaceBootstrap(input_root, workspace_root, result, discovery, registry)


def run_subprocess(
    args: Sequence[str | os.PathLike[str]],
    *,
    cwd: Path = REPOSITORY_ROOT,
    env: Mapping[str, str] | None = None,
    timeout: float = 30.0,
) -> subprocess.CompletedProcess[str]:
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    process_env["PYTHONDONTWRITEBYTECODE"] = "1"
    process_env["PYTHONIOENCODING"] = "utf-8"
    process_env["PYTHONUTF8"] = "1"
    return subprocess.run(
        [os.fspath(value) for value in args],
        cwd=cwd,
        env=process_env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=timeout,
    )


def run_qbcore_cli(*args: str, cwd: Path = REPOSITORY_ROOT) -> subprocess.CompletedProcess[str]:
    existing_pythonpath = os.environ.get("PYTHONPATH")
    pythonpath = str(SCRIPTS_ROOT)
    if existing_pythonpath:
        pythonpath = os.pathsep.join((pythonpath, existing_pythonpath))
    return run_subprocess(
        (sys.executable, "-m", "qbcore.cli", *args),
        cwd=cwd,
        env={"PYTHONPATH": pythonpath},
    )
