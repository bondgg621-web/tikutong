from __future__ import annotations

import ast
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

import pytest

from m2_helpers import (
    UUIDSequence,
    bootstrap_m1_workspace,
    fixed_now,
    tree_snapshot,
    write_exact_bytes,
)
from qbcore.cli import run_inventory
from qbcore.parse_service import (
    ResolvedSource,
    SourceResolutionError,
    resolve_single_choice_source,
)
from qbcore.single_choice_parser import ParseResult


def _source_id(bootstrapped) -> str:
    return bootstrapped.registry["sources"][0]["source_id"]


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _registry_path(bootstrapped) -> Path:
    return bootstrapped.workspace_root / "registry" / "sources.json"


def _project_path(bootstrapped) -> Path:
    return bootstrapped.workspace_root / "project.json"


def _assert_read_only_call(
    *,
    input_root: Path,
    workspace_root: Path,
    source_id: str,
) -> ResolvedSource:
    input_before = tree_snapshot(input_root)
    workspace_before = tree_snapshot(workspace_root)
    result = resolve_single_choice_source(
        input_root=input_root,
        workspace_root=workspace_root,
        source_id=source_id,
    )
    assert tree_snapshot(input_root) == input_before
    assert tree_snapshot(workspace_root) == workspace_before
    return result


def _assert_resolution_error(
    *,
    input_root: Path,
    workspace_root: Path,
    source_id: str,
    message: str,
    issue_code: str | None = None,
) -> SourceResolutionError:
    input_before = tree_snapshot(input_root) if input_root.is_dir() else None
    workspace_before = tree_snapshot(workspace_root) if workspace_root.is_dir() else None
    with pytest.raises(SourceResolutionError) as caught:
        resolve_single_choice_source(
            input_root=input_root,
            workspace_root=workspace_root,
            source_id=source_id,
        )
    error = caught.value
    assert str(error) == message
    assert error.issue_code == issue_code
    assert str(input_root) not in str(error)
    assert str(workspace_root) not in str(error)
    if input_before is not None:
        assert tree_snapshot(input_root) == input_before
    if workspace_before is not None:
        assert tree_snapshot(workspace_root) == workspace_before
    return error


def _replace_source_bytes_and_reinventory(bootstrapped, payload: bytes) -> tuple[str, dict]:
    source_path = (
        bootstrapped.input_root
        / bootstrapped.registry["sources"][0]["current_relative_path"]
    )
    source_path.write_bytes(payload)
    run_inventory(
        input_root=bootstrapped.input_root,
        workspace_root=bootstrapped.workspace_root,
        now=fixed_now,
        uuid_factory=UUIDSequence(100),
    )
    registry = json.loads(_registry_path(bootstrapped).read_text(encoding="utf-8"))
    return registry["sources"][0]["source_id"], registry


def test_valid_registry_lookup_decodes_hashes_parses_and_changes_nothing(tmp_path: Path) -> None:
    bootstrapped = bootstrap_m1_workspace(tmp_path, fixture_names=("strict-two.txt",))
    source = bootstrapped.registry["sources"][0]

    resolved = _assert_read_only_call(
        input_root=bootstrapped.input_root,
        workspace_root=bootstrapped.workspace_root,
        source_id=source["source_id"],
    )

    assert isinstance(resolved, ResolvedSource)
    assert resolved.source_id == source["source_id"]
    assert resolved.source_revision == source["revision"]
    assert resolved.relative_path == "strict-two.txt"
    assert resolved.content_hash == source["current_content_hash"]
    assert resolved.text == (
        bootstrapped.input_root / "strict-two.txt"
    ).read_text(encoding="utf-8")
    assert isinstance(resolved.parse_result, ParseResult)
    assert len(resolved.parse_result.questions) == 2


@pytest.mark.parametrize(
    "relative_path",
    ("answers.MD", "declared-source.MarkDown", "plain.TXT"),
)
def test_supported_suffixes_are_case_insensitive_and_source_id_declares_role(
    tmp_path: Path,
    relative_path: str,
) -> None:
    bootstrapped = bootstrap_m1_workspace(tmp_path, fixture_names=("strict-two.txt",))
    original = bootstrapped.input_root / "strict-two.txt"
    renamed = bootstrapped.input_root / relative_path
    renamed.write_bytes(original.read_bytes())
    original.unlink()
    run_inventory(
        input_root=bootstrapped.input_root,
        workspace_root=bootstrapped.workspace_root,
        now=fixed_now,
        uuid_factory=UUIDSequence(100),
    )
    registry = json.loads(_registry_path(bootstrapped).read_text(encoding="utf-8"))
    source = registry["sources"][0]

    resolved = _assert_read_only_call(
        input_root=bootstrapped.input_root,
        workspace_root=bootstrapped.workspace_root,
        source_id=source["source_id"],
    )

    assert resolved.relative_path == relative_path
    assert len(resolved.parse_result.questions) == 2


@pytest.mark.parametrize(
    "source_id",
    (
        "00000000-0000-4000-8000-000000000099",
        "NOT-A-UUID",
        "00000000-0000-4000-8000-00000000000A",
    ),
    ids=("missing", "malformed", "uppercase"),
)
def test_missing_or_noncanonical_source_id_is_rejected(
    tmp_path: Path,
    source_id: str,
) -> None:
    bootstrapped = bootstrap_m1_workspace(tmp_path, fixture_names=("strict-two.txt",))
    expected = (
        "source_id is not present exactly once in registry"
        if source_id.endswith("099")
        else "source_id must be a canonical lowercase UUID"
    )
    _assert_resolution_error(
        input_root=bootstrapped.input_root,
        workspace_root=bootstrapped.workspace_root,
        source_id=source_id,
        message=expected,
    )


def test_duplicate_source_id_is_rejected(tmp_path: Path) -> None:
    bootstrapped = bootstrap_m1_workspace(tmp_path, fixture_names=("strict-two.txt",))
    registry = deepcopy(bootstrapped.registry)
    registry["sources"].append(deepcopy(registry["sources"][0]))
    _write_json(_registry_path(bootstrapped), registry)

    _assert_resolution_error(
        input_root=bootstrapped.input_root,
        workspace_root=bootstrapped.workspace_root,
        source_id=_source_id(bootstrapped),
        message="source_id is not present exactly once in registry",
    )


def test_missing_presence_is_rejected(tmp_path: Path) -> None:
    bootstrapped = bootstrap_m1_workspace(tmp_path, fixture_names=("strict-two.txt",))
    registry = deepcopy(bootstrapped.registry)
    registry["sources"][0]["presence"] = "missing"
    _write_json(_registry_path(bootstrapped), registry)

    _assert_resolution_error(
        input_root=bootstrapped.input_root,
        workspace_root=bootstrapped.workspace_root,
        source_id=_source_id(bootstrapped),
        message="registered source is not present",
    )


@pytest.mark.parametrize("missing_name", ("workspace", "project", "registry"))
def test_initialized_workspace_documents_are_required(
    tmp_path: Path,
    missing_name: str,
) -> None:
    bootstrapped = bootstrap_m1_workspace(tmp_path, fixture_names=("strict-two.txt",))
    if missing_name == "workspace":
        workspace_root = tmp_path / "not-initialized"
        message = "initialized workspace is required"
    elif missing_name == "project":
        _project_path(bootstrapped).unlink()
        workspace_root = bootstrapped.workspace_root
        message = "workspace project document is invalid"
    else:
        _registry_path(bootstrapped).unlink()
        workspace_root = bootstrapped.workspace_root
        message = "source registry document is invalid"

    _assert_resolution_error(
        input_root=bootstrapped.input_root,
        workspace_root=workspace_root,
        source_id=_source_id(bootstrapped),
        message=message,
    )


@pytest.mark.parametrize(
    "document",
    ("project-json", "registry-json", "project-schema", "registry-schema"),
)
def test_invalid_workspace_json_or_schema_is_rejected(
    tmp_path: Path,
    document: str,
) -> None:
    bootstrapped = bootstrap_m1_workspace(tmp_path, fixture_names=("strict-two.txt",))
    if document == "project-json":
        _project_path(bootstrapped).write_bytes(b"{not-json")
        message = "workspace project document is invalid"
    elif document == "registry-json":
        _registry_path(bootstrapped).write_bytes(b"\xff")
        message = "source registry document is invalid"
    elif document == "project-schema":
        project = json.loads(_project_path(bootstrapped).read_text(encoding="utf-8"))
        project.pop("dataset_id")
        _write_json(_project_path(bootstrapped), project)
        message = "workspace project document is invalid"
    else:
        registry = deepcopy(bootstrapped.registry)
        registry["registry_revision"] = -1
        _write_json(_registry_path(bootstrapped), registry)
        message = "source registry document is invalid"

    _assert_resolution_error(
        input_root=bootstrapped.input_root,
        workspace_root=bootstrapped.workspace_root,
        source_id=_source_id(bootstrapped),
        message=message,
    )


def test_invalid_root_policy_is_sanitized(tmp_path: Path) -> None:
    bootstrapped = bootstrap_m1_workspace(
        tmp_path / "valid",
        fixture_names=("strict-two.txt",),
    )
    missing_input = tmp_path / "secret-missing-input"
    _assert_resolution_error(
        input_root=missing_input,
        workspace_root=bootstrapped.workspace_root,
        source_id=_source_id(bootstrapped),
        message="source resolution roots are invalid",
    )


def test_project_and_registry_dataset_ids_must_match(tmp_path: Path) -> None:
    bootstrapped = bootstrap_m1_workspace(tmp_path, fixture_names=("strict-two.txt",))
    registry = deepcopy(bootstrapped.registry)
    registry["dataset_id"] = "00000000-0000-4000-8000-000000000099"
    _write_json(_registry_path(bootstrapped), registry)

    _assert_resolution_error(
        input_root=bootstrapped.input_root,
        workspace_root=bootstrapped.workspace_root,
        source_id=_source_id(bootstrapped),
        message="workspace dataset_id does not match source registry",
    )


def test_unsupported_extension_has_frozen_issue_code(tmp_path: Path) -> None:
    bootstrapped = bootstrap_m1_workspace(tmp_path, fixture_names=("strict-two.txt",))
    registry = deepcopy(bootstrapped.registry)
    source = registry["sources"][0]
    unsupported = bootstrapped.input_root / "synthetic.PDF"
    unsupported.write_bytes((bootstrapped.input_root / "strict-two.txt").read_bytes())
    source["current_relative_path"] = unsupported.name
    _write_json(_registry_path(bootstrapped), registry)

    _assert_resolution_error(
        input_root=bootstrapped.input_root,
        workspace_root=bootstrapped.workspace_root,
        source_id=source["source_id"],
        message="registered source type is unsupported",
        issue_code="QB-SOURCE-UNSUPPORTED",
    )


@pytest.mark.parametrize("kind", ("absent", "directory", "unreadable"))
def test_source_read_failures_have_frozen_issue_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    bootstrapped = bootstrap_m1_workspace(tmp_path, fixture_names=("strict-two.txt",))
    source_path = bootstrapped.input_root / "strict-two.txt"
    if kind == "absent":
        source_path.unlink()
    elif kind == "directory":
        source_path.unlink()
        source_path.mkdir()
    else:
        original_open = Path.open

        def deny_source(path: Path, *args, **kwargs):
            if path == source_path and args and args[0] == "rb":
                raise PermissionError("sensitive operating-system detail")
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr(Path, "open", deny_source)

    _assert_resolution_error(
        input_root=bootstrapped.input_root,
        workspace_root=bootstrapped.workspace_root,
        source_id=_source_id(bootstrapped),
        message="registered source could not be read",
        issue_code="QB-SOURCE-READ-FAILED",
    )


def test_stale_content_hash_requires_inventory_without_registry_update(
    tmp_path: Path,
) -> None:
    bootstrapped = bootstrap_m1_workspace(tmp_path, fixture_names=("strict-two.txt",))
    source_path = bootstrapped.input_root / "strict-two.txt"
    source_path.write_bytes(source_path.read_bytes() + b"\nsynthetic stale bytes\n")

    _assert_resolution_error(
        input_root=bootstrapped.input_root,
        workspace_root=bootstrapped.workspace_root,
        source_id=_source_id(bootstrapped),
        message="registered source hash is stale; rerun inventory",
    )


@pytest.mark.parametrize(
    "unsafe_path",
    (
        "/absolute.txt",
        "C:/drive.txt",
        "//server/share.txt",
        "../escape.txt",
        "a/./source.txt",
        "a//source.txt",
        "stream.txt:secret",
        "a\\source.txt",
        "control\x01.txt",
        "bad<name>.txt",
        "CON.txt",
        "folder./source.txt",
        "folder /source.txt",
    ),
    ids=(
        "absolute",
        "drive",
        "unc",
        "parent",
        "dot",
        "empty-segment",
        "ads",
        "backslash",
        "control",
        "invalid-character",
        "reserved-device",
        "trailing-dot",
        "trailing-space",
    ),
)
def test_tampered_unsafe_registry_paths_are_rejected(
    tmp_path: Path,
    unsafe_path: str,
) -> None:
    bootstrapped = bootstrap_m1_workspace(tmp_path, fixture_names=("strict-two.txt",))
    registry = deepcopy(bootstrapped.registry)
    registry["sources"][0]["current_relative_path"] = unsafe_path
    _write_json(_registry_path(bootstrapped), registry)

    error = _assert_resolution_error(
        input_root=bootstrapped.input_root,
        workspace_root=bootstrapped.workspace_root,
        source_id=_source_id(bootstrapped),
        message="registered source path is unsafe",
    )
    assert unsafe_path not in str(error)


def test_invalid_utf8_is_a_sanitized_read_failure(tmp_path: Path) -> None:
    bootstrapped = bootstrap_m1_workspace(tmp_path, fixture_names=("strict-two.txt",))
    payload = b"synthetic secret prefix\xffsynthetic secret suffix"
    source_id, _ = _replace_source_bytes_and_reinventory(bootstrapped, payload)

    error = _assert_resolution_error(
        input_root=bootstrapped.input_root,
        workspace_root=bootstrapped.workspace_root,
        source_id=source_id,
        message="registered source could not be read",
        issue_code="QB-SOURCE-READ-FAILED",
    )
    assert "synthetic secret" not in str(error)


def test_utf8_bom_and_newline_byte_forms_have_equal_parse_results(
    tmp_path: Path,
) -> None:
    logical = (
        "1. [single_choice] Which newline form is synthetic?\n"
        "- A. First\n"
        "- B. Second\n"
    )
    byte_forms = (
        logical.encode("utf-8"),
        b"\xef\xbb\xbf" + logical.replace("\n", "\r\n").encode("utf-8"),
        logical.replace("\n", "\r").encode("utf-8"),
    )
    resolved: list[ResolvedSource] = []
    for index, payload in enumerate(byte_forms):
        bootstrapped = bootstrap_m1_workspace(
            tmp_path / str(index),
            fixture_names=("strict-two.txt",),
            uuid_start=10 * index + 1,
        )
        source_id, _ = _replace_source_bytes_and_reinventory(bootstrapped, payload)
        resolved.append(
            _assert_read_only_call(
                input_root=bootstrapped.input_root,
                workspace_root=bootstrapped.workspace_root,
                source_id=source_id,
            )
        )

    assert resolved[0].parse_result == resolved[1].parse_result == resolved[2].parse_result
    assert len({item.content_hash for item in resolved}) == 3
    assert all(not item.text.startswith("\ufeff") for item in resolved)


def test_only_the_explicit_registry_source_is_read_from_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrapped = bootstrap_m1_workspace(tmp_path, fixture_names=("strict-two.txt",))
    adjacent = write_exact_bytes(
        bootstrapped.input_root / "answers.txt",
        b"sensitive adjacent bytes",
    )
    source_path = bootstrapped.input_root / "strict-two.txt"
    opened_input_paths: list[Path] = []
    original_open = Path.open

    def track_open(path: Path, *args, **kwargs):
        try:
            path.resolve(strict=False).relative_to(bootstrapped.input_root.resolve())
        except ValueError:
            pass
        else:
            opened_input_paths.append(path.resolve(strict=False))
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", track_open)
    resolved = resolve_single_choice_source(
        input_root=bootstrapped.input_root,
        workspace_root=bootstrapped.workspace_root,
        source_id=_source_id(bootstrapped),
    )

    assert resolved.relative_path == source_path.name
    assert set(opened_input_paths) == {source_path.resolve()}
    assert adjacent.read_bytes() == b"sensitive adjacent bytes"


def test_only_project_and_registry_are_read_from_existing_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrapped = bootstrap_m1_workspace(tmp_path, fixture_names=("strict-two.txt",))
    opened_workspace_paths: list[Path] = []
    original_open = Path.open

    def track_open(path: Path, *args, **kwargs):
        try:
            path.resolve(strict=False).relative_to(bootstrapped.workspace_root.resolve())
        except ValueError:
            pass
        else:
            opened_workspace_paths.append(path.resolve(strict=False))
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", track_open)
    resolve_single_choice_source(
        input_root=bootstrapped.input_root,
        workspace_root=bootstrapped.workspace_root,
        source_id=_source_id(bootstrapped),
    )

    assert set(opened_workspace_paths) == {
        _project_path(bootstrapped).resolve(),
        _registry_path(bootstrapped).resolve(),
    }


def test_parse_service_integrates_only_the_frozen_candidate_materializer() -> None:
    import qbcore.parse_service as parse_service

    tree = ast.parse(Path(parse_service.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert "qbcore.candidate_materializer" in imported
    assert not {
        "qbcore.decision",
        "qbcore.identity_migration",
        "qbcore.review",
    } & imported


def _make_symlink(link: Path, target: Path, *, directory: bool) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (NotImplementedError, OSError) as error:
        pytest.skip(
            f"symbolic links are unavailable on this platform: {type(error).__name__}"
        )


@pytest.mark.parametrize("link_kind", ("file", "directory"))
def test_symlink_escape_is_rejected_where_supported(
    tmp_path: Path,
    link_kind: str,
) -> None:
    bootstrapped = bootstrap_m1_workspace(
        tmp_path / "case",
        fixture_names=("strict-two.txt",),
    )
    external = tmp_path / "outside"
    external.mkdir()
    external_file = write_exact_bytes(
        external / "outside.txt",
        (bootstrapped.input_root / "strict-two.txt").read_bytes(),
    )
    registry = deepcopy(bootstrapped.registry)
    if link_kind == "file":
        link = bootstrapped.input_root / "linked.txt"
        _make_symlink(link, external_file, directory=False)
        registry["sources"][0]["current_relative_path"] = link.name
    else:
        link = bootstrapped.input_root / "linked"
        _make_symlink(link, external, directory=True)
        registry["sources"][0]["current_relative_path"] = "linked/outside.txt"
    _write_json(_registry_path(bootstrapped), registry)

    _assert_resolution_error(
        input_root=bootstrapped.input_root,
        workspace_root=bootstrapped.workspace_root,
        source_id=_source_id(bootstrapped),
        message="registered source path is unsafe",
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows directory junction semantics only")
def test_windows_junction_escape_is_rejected_where_supported(tmp_path: Path) -> None:
    bootstrapped = bootstrap_m1_workspace(
        tmp_path / "case",
        fixture_names=("strict-two.txt",),
    )
    external = tmp_path / "outside"
    external.mkdir()
    write_exact_bytes(
        external / "outside.txt",
        (bootstrapped.input_root / "strict-two.txt").read_bytes(),
    )
    junction = bootstrapped.input_root / "junction"
    completed = subprocess.run(
        [
            "cmd.exe",
            "/d",
            "/c",
            "mklink",
            "/J",
            os.fspath(junction),
            os.fspath(external),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        pytest.skip(
            f"directory junction creation unavailable: exit {completed.returncode}"
        )
    registry = deepcopy(bootstrapped.registry)
    registry["sources"][0]["current_relative_path"] = "junction/outside.txt"
    _write_json(_registry_path(bootstrapped), registry)

    _assert_resolution_error(
        input_root=bootstrapped.input_root,
        workspace_root=bootstrapped.workspace_root,
        source_id=_source_id(bootstrapped),
        message="registered source path is unsafe",
    )


def test_hash_is_sha256_of_exact_raw_bytes(tmp_path: Path) -> None:
    bootstrapped = bootstrap_m1_workspace(tmp_path, fixture_names=("strict-two.txt",))
    payload = (
        b"\xef\xbb\xbf1. [single_choice] Synthetic?\r\n"
        b"- A. Yes\r\n"
        b"- B. No\r\n"
    )
    source_id, registry = _replace_source_bytes_and_reinventory(
        bootstrapped,
        payload,
    )

    resolved = resolve_single_choice_source(
        input_root=bootstrapped.input_root,
        workspace_root=bootstrapped.workspace_root,
        source_id=source_id,
    )

    assert resolved.content_hash == sha256(payload).hexdigest()
    assert resolved.content_hash == registry["sources"][0]["current_content_hash"]
    assert resolved.text.startswith("1. [single_choice]")
