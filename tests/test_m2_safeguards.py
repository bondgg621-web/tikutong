from __future__ import annotations

import ast
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import textwrap

import pytest

from conftest import SKILL_ROOT
from m2_helpers import UUIDSequence, fixed_now, tree_snapshot
from qbcore.cli import main, run_inventory
from qbcore.parse_service import SourceResolutionError, run_single_choice_parse


M2_RUNTIME_FILES = (
    "candidate_materializer.py",
    "cli.py",
    "parse_contracts.py",
    "parse_service.py",
    "single_choice_parser.py",
    "text_normalization.py",
    "workspace.py",
)
FORBIDDEN_IMPORT_ROOTS = {
    "ensurepip",
    "ftplib",
    "httpx",
    "pip",
    "pymongo",
    "requests",
    "smtplib",
    "socket",
    "sqlite3",
    "sqlalchemy",
    "subprocess",
    "tempfile",
    "urllib",
    "venv",
}
DIRECT_MUTATION_METHODS = {
    "chmod",
    "chown",
    "link",
    "makedirs",
    "mkdir",
    "remove",
    "rename",
    "replace",
    "rmdir",
    "symlink",
    "touch",
    "truncate",
    "unlink",
    "write_bytes",
    "write_text",
}
PATH_MUTATION_METHODS = {
    "chmod",
    "chown",
    "hardlink_to",
    "mkdir",
    "rename",
    "rmdir",
    "symlink_to",
    "touch",
    "truncate",
    "unlink",
    "write_bytes",
    "write_text",
}
ALLOWED_DIRECT_MUTATION_CONTEXTS = {
    "cli.py:_append_event_log:direct-write",
    "workspace.py:initialize:direct-write",
    "workspace.py:write_json_atomic:direct-write",
    "workspace.py:_stage_json_payload:direct-write",
    "workspace.py:_publish_staged_json:direct-write",
    "workspace.py:_snapshot_existing_json_target:direct-write",
    "workspace.py:_discard_json_snapshot:direct-write",
    "workspace.py:_restore_json_snapshot:direct-write",
    "workspace.py:_publish_staged_json_no_overwrite:direct-write",
    "workspace.py:write_parse_run_artifact:direct-write",
    "workspace.py:_remove_invalid_candidate_target:direct-write",
    "workspace.py:_discard_safe_candidate_staging:direct-write",
}


def _write_json(path: Path, document: dict) -> None:
    path.write_text(
        json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def _registry(workspace_root: Path) -> dict:
    return json.loads(
        (workspace_root / "registry" / "sources.json").read_text(encoding="utf-8")
    )


def _unexpected_uuid():
    raise AssertionError("UUID allocation must not occur")


def _static_safeguard_violations(name: str, source: str) -> list[str]:
    tree = ast.parse(source, filename=name)
    violations: list[str] = []
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    path_aliases = {"Path"}
    pathlib_aliases = {"pathlib"}
    open_aliases = {"open"}
    mutation_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "pathlib":
                    pathlib_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "pathlib":
            for alias in node.names:
                if alias.name == "Path":
                    path_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "builtins":
            for alias in node.names:
                if alias.name == "open":
                    open_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "os":
            for alias in node.names:
                if alias.name in DIRECT_MUTATION_METHODS:
                    mutation_aliases.add(alias.asname or alias.name)

    assignments = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)]
    changed = True
    while changed:
        changed = False
        for node in assignments:
            targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if not targets:
                continue
            is_open_alias = (
                isinstance(node.value, ast.Name) and node.value.id in open_aliases
            ) or (
                isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "builtins"
                and node.value.attr == "open"
            )
            is_mutation_alias = (
                isinstance(node.value, ast.Name)
                and node.value.id in mutation_aliases
            ) or (
                isinstance(node.value, ast.Attribute)
                and (
                    node.value.attr in PATH_MUTATION_METHODS
                    or (
                        isinstance(node.value.value, ast.Name)
                        and node.value.value.id == "os"
                        and node.value.attr in DIRECT_MUTATION_METHODS
                    )
                )
            )
            for target in targets:
                if is_open_alias and target not in open_aliases:
                    open_aliases.add(target)
                    changed = True
                if is_mutation_alias and target not in mutation_aliases:
                    mutation_aliases.add(target)
                    changed = True

    def add(node: ast.AST, kind: str) -> None:
        current = node
        context = "<module>"
        while current in parents:
            current = parents[current]
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                context = current.name
                break
        violations.append(f"{name}:{context}:{kind}")

    def literal_mode(node: ast.Call) -> str | None:
        mode_node = node.args[1] if len(node.args) > 1 else None
        for keyword in node.keywords:
            if keyword.arg == "mode":
                mode_node = keyword.value
        if isinstance(mode_node, ast.Constant) and isinstance(mode_node.value, str):
            return mode_node.value
        return None

    def literal_home_argument(node: ast.Call) -> bool:
        return bool(
            node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and node.args[0].value.startswith("~")
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported = {alias.name.split(".", 1)[0] for alias in node.names}
            if imported & FORBIDDEN_IMPORT_ROOTS:
                add(node, "forbidden-import")
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".", 1)[0] in FORBIDDEN_IMPORT_ROOTS:
                add(node, "forbidden-import")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {"eval", "exec", "compile", "__import__"}:
                add(node, "source-execution")
            if node.func.id in open_aliases:
                mode = literal_mode(node)
                if mode is not None and any(flag in mode for flag in "wax+"):
                    add(node, "direct-write")
            if node.func.id in mutation_aliases:
                add(node, "direct-write")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id in path_aliases
                and node.func.attr == "home"
            ):
                add(node, "implicit-home")
            if (
                isinstance(node.func.value, ast.Attribute)
                and isinstance(node.func.value.value, ast.Name)
                and node.func.value.value.id in pathlib_aliases
                and node.func.value.attr == "Path"
                and node.func.attr == "home"
            ):
                add(node, "implicit-home")
            if node.func.attr == "expanduser":
                if literal_home_argument(node) or (
                    isinstance(node.func.value, ast.Call)
                    and isinstance(node.func.value.func, ast.Name)
                    and node.func.value.func.id in path_aliases
                    and literal_home_argument(node.func.value)
                ):
                    add(node, "implicit-home")
            if (
                node.func.attr in {"getenv", "get"}
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value in {"HOME", "USERPROFILE"}
            ):
                add(node, "implicit-home")
            if node.func.attr in PATH_MUTATION_METHODS or (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "os"
                and node.func.attr in DIRECT_MUTATION_METHODS
            ):
                add(node, "direct-write")
            if node.func.attr == "open" and node.args:
                mode = node.args[0]
                if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
                    if any(flag in mode.value for flag in "wax+"):
                        add(node, "direct-write")
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "builtins"
                and node.func.attr == "open"
            ):
                mode = literal_mode(node)
                if mode is not None and any(flag in mode for flag in "wax+"):
                    add(node, "direct-write")
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "os"
            and node.value.attr == "environ"
            and isinstance(node.slice, ast.Constant)
            and node.slice.value in {"HOME", "USERPROFILE"}
        ):
            add(node, "implicit-home")
    return sorted(set(violations))


def test_static_guard_detects_home_temp_and_direct_write_examples() -> None:
    assert _static_safeguard_violations(
        "bad.py",
        "from pathlib import Path\nPath.home().joinpath('leak').write_text('x')\n",
    ) == ["bad.py:<module>:direct-write", "bad.py:<module>:implicit-home"]
    assert _static_safeguard_violations(
        "bad.py",
        "import tempfile\ntempfile.NamedTemporaryFile()\n",
    ) == ["bad.py:<module>:forbidden-import"]
    assert _static_safeguard_violations(
        "bad.py",
        "open('outside', 'wb')\n",
    ) == ["bad.py:<module>:direct-write"]
    assert _static_safeguard_violations(
        "bad.py",
        "import builtins\nbuiltins.open('outside', mode='wb')\n",
    ) == ["bad.py:<module>:direct-write"]
    assert _static_safeguard_violations(
        "bad.py",
        "from builtins import open as file_open\nfile_open('outside', 'wb')\n",
    ) == ["bad.py:<module>:direct-write"]
    assert _static_safeguard_violations(
        "bad.py",
        "from pathlib import Path\nPath('outside').unlink()\n",
    ) == ["bad.py:<module>:direct-write"]
    for source in (
        "from pathlib import Path as P\nP.home()\n",
        "import pathlib as paths\npaths.Path.home()\n",
        "from pathlib import Path\nPath('~/cache').expanduser()\n",
        "import os\nos.getenv('HOME')\n",
        "import os\nos.environ.get('USERPROFILE')\n",
        "import os\nos.environ['HOME']\n",
    ):
        assert _static_safeguard_violations("bad.py", source) == [
            "bad.py:<module>:implicit-home"
        ]


def test_m2_runtime_has_no_remote_process_package_database_or_text_execution() -> None:
    runtime_root = SKILL_ROOT / "scripts" / "qbcore"
    violations: list[str] = []
    for name in M2_RUNTIME_FILES:
        file_violations = _static_safeguard_violations(
            name,
            (runtime_root / name).read_text(encoding="utf-8"),
        )
        violations.extend(
            violation
            for violation in file_violations
            if violation not in ALLOWED_DIRECT_MUTATION_CONTEXTS
        )

    assert violations == []


def test_inventory_and_parse_write_only_inside_explicit_workspace(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "input"
    workspace_root = tmp_path / "workspace"
    input_root.mkdir()
    (input_root / "synthetic.txt").write_text(
        "1. [single_choice] Synthetic write boundary?\n- A. Yes\n- B. No\n",
        encoding="utf-8",
    )
    runner = tmp_path / "audit_runner.py"
    runner.write_text(
        textwrap.dedent(
            """
            from datetime import datetime, timezone
            import json
            import os
            from pathlib import Path
            import sys
            from uuid import UUID

            INPUT_ROOT = Path(sys.argv[1])
            WORKSPACE_ROOT = Path(sys.argv[2])
            WORKSPACE_REAL = os.path.realpath(WORKSPACE_ROOT)
            WRITE_MASK = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
            WRITE_EVENTS = []

            def require_workspace(path, event):
                if isinstance(path, int):
                    return
                value = os.path.realpath(os.path.abspath(os.fspath(path)))
                try:
                    inside = os.path.commonpath((value, WORKSPACE_REAL)) == WORKSPACE_REAL
                except ValueError:
                    inside = False
                if not inside:
                    raise RuntimeError(f"write escaped workspace via {event}")
                WRITE_EVENTS.append(event)

            def audit(event, args):
                if event == "open":
                    path, mode, flags = args
                    writing = (
                        isinstance(mode, str) and any(flag in mode for flag in "wax+")
                    ) or (isinstance(flags, int) and bool(flags & WRITE_MASK))
                    if writing:
                        require_workspace(path, event)
                elif event in {
                    "os.mkdir", "os.remove", "os.rmdir", "os.chmod",
                    "os.chown", "os.truncate", "os.utime",
                }:
                    require_workspace(args[0], event)
                elif event in {"os.link", "os.rename", "os.symlink"}:
                    require_workspace(args[0], event)
                    require_workspace(args[1], event)

            sys.addaudithook(audit)

            from qbcore.cli import run_inventory
            from qbcore.parse_service import run_single_choice_parse

            class UUIDSequence:
                def __init__(self, value):
                    self.value = value
                def __call__(self):
                    result = UUID(int=self.value, version=4)
                    self.value += 1
                    return result

            def now():
                return datetime(2026, 8, 14, tzinfo=timezone.utc)

            run_inventory(
                input_root=INPUT_ROOT,
                workspace_root=WORKSPACE_ROOT,
                now=now,
                uuid_factory=UUIDSequence(2900),
            )
            registry = json.loads(
                (WORKSPACE_ROOT / "registry" / "sources.json").read_text(encoding="utf-8")
            )
            result = run_single_choice_parse(
                input_root=INPUT_ROOT,
                workspace_root=WORKSPACE_ROOT,
                source_id=registry["sources"][0]["source_id"],
                now=now,
                uuid_factory=UUIDSequence(2950),
            )
            blocked_probe = False
            try:
                with open(INPUT_ROOT / "must-not-write.bin", "wb") as stream:
                    stream.write(b"blocked")
            except RuntimeError:
                blocked_probe = True
            print(json.dumps({
                "blocked_probe": blocked_probe,
                "status": result.status,
                "write_events": sorted(set(WRITE_EVENTS)),
            }, sort_keys=True))
            """
        ).lstrip(),
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONPATH"] = str(SKILL_ROOT / "scripts")

    completed = subprocess.run(
        [sys.executable, str(runner), str(input_root), str(workspace_root)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["blocked_probe"] is True
    assert payload["status"] == "complete"
    assert not (input_root / "must-not-write.bin").exists()
    assert {"open", "os.link", "os.mkdir", "os.remove", "os.rename"} <= set(
        payload["write_events"]
    )


def test_parse_command_output_and_run_metadata_do_not_copy_question_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_root = tmp_path / "input"
    workspace_root = tmp_path / "workspace"
    input_root.mkdir()
    private_markers = (
        "PRIVATE-STEM-MARKER",
        "PRIVATE-OPTION-ONE",
        "PRIVATE-OPTION-TWO",
    )
    (input_root / "private.txt").write_text(
        "1. [single_choice] PRIVATE-STEM-MARKER\n"
        "- A. PRIVATE-OPTION-ONE\n"
        "- B. PRIVATE-OPTION-TWO\n",
        encoding="utf-8",
    )
    run_inventory(
        input_root=input_root,
        workspace_root=workspace_root,
        now=fixed_now,
        uuid_factory=UUIDSequence(3000),
    )
    source_id = _registry(workspace_root)["sources"][0]["source_id"]
    monkeypatch.setattr("qbcore.cli.system_now", fixed_now)
    monkeypatch.setattr("qbcore.cli.system_uuid", UUIDSequence(3100))

    assert main(
        [
            "parse-single-choice",
            "--input-root",
            str(input_root),
            "--workspace-root",
            str(workspace_root),
            "--source-id",
            source_id,
        ]
    ) == 0

    captured = capsys.readouterr()
    command_output = captured.out + captured.err
    assert all(marker not in command_output for marker in private_markers)
    non_candidate_state = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in workspace_root.rglob("*")
        if path.is_file() and "candidates" not in path.parts
    )
    assert all(marker not in non_candidate_state for marker in private_markers)


def test_workspace_inside_input_is_pruned_before_and_after_parse(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    workspace_root = input_root / ".workspace"
    input_root.mkdir()
    source = input_root / "synthetic.txt"
    source.write_text(
        "1. [single_choice] Synthetic nested workspace?\n"
        "- A. Yes\n"
        "- B. No\n",
        encoding="utf-8",
    )
    source_hash = sha256(source.read_bytes()).hexdigest()
    first = run_inventory(
        input_root=input_root,
        workspace_root=workspace_root,
        now=fixed_now,
        uuid_factory=UUIDSequence(3200),
    )
    source_id = _registry(workspace_root)["sources"][0]["source_id"]
    parsed = run_single_choice_parse(
        input_root=input_root,
        workspace_root=workspace_root,
        source_id=source_id,
        now=fixed_now,
        uuid_factory=UUIDSequence(3300),
    )
    second = run_inventory(
        input_root=input_root,
        workspace_root=workspace_root,
        now=fixed_now,
        uuid_factory=UUIDSequence(3400),
    )

    assert first.status == parsed.status == second.status == "complete"
    sources = _registry(workspace_root)["sources"]
    assert [source["current_relative_path"] for source in sources] == ["synthetic.txt"]
    assert sha256(source.read_bytes()).hexdigest() == source_hash


def test_unicode_filename_and_uppercase_extension_parse_without_path_rewrite(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "input"
    workspace_root = tmp_path / "workspace"
    input_root.mkdir()
    relative_path = "合成-Cafe\u0301.MD"
    (input_root / relative_path).write_text(
        "1. [single_choice] Unicode synthetic path?\n"
        "- A. First\n"
        "- B. Second\n",
        encoding="utf-8",
    )
    run_inventory(
        input_root=input_root,
        workspace_root=workspace_root,
        now=fixed_now,
        uuid_factory=UUIDSequence(3500),
    )
    source = _registry(workspace_root)["sources"][0]

    result = run_single_choice_parse(
        input_root=input_root,
        workspace_root=workspace_root,
        source_id=source["source_id"],
        now=fixed_now,
        uuid_factory=UUIDSequence(3600),
    )

    assert result.status == "complete"
    assert source["current_relative_path"] == relative_path


def test_tampered_registry_traversal_fails_before_uuid_or_workspace_mutation(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "input"
    workspace_root = tmp_path / "workspace"
    input_root.mkdir()
    source = input_root / "synthetic.txt"
    source.write_text(
        "1. [single_choice] Synthetic traversal guard?\n- A. Yes\n- B. No\n",
        encoding="utf-8",
    )
    run_inventory(
        input_root=input_root,
        workspace_root=workspace_root,
        now=fixed_now,
        uuid_factory=UUIDSequence(3700),
    )
    registry_path = workspace_root / "registry" / "sources.json"
    registry = _registry(workspace_root)
    source_id = registry["sources"][0]["source_id"]
    registry["sources"][0]["current_relative_path"] = "../synthetic.txt"
    _write_json(registry_path, registry)
    before = tree_snapshot(workspace_root)

    with pytest.raises(SourceResolutionError, match="path is unsafe"):
        run_single_choice_parse(
            input_root=input_root,
            workspace_root=workspace_root,
            source_id=source_id,
            now=fixed_now,
            uuid_factory=_unexpected_uuid,
        )

    assert tree_snapshot(workspace_root) == before


def test_read_only_source_is_parsed_without_mutation(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    workspace_root = tmp_path / "workspace"
    input_root.mkdir()
    source = input_root / "readonly.txt"
    source.write_text(
        "1. [single_choice] Synthetic read-only source?\n- A. Yes\n- B. No\n",
        encoding="utf-8",
    )
    run_inventory(
        input_root=input_root,
        workspace_root=workspace_root,
        now=fixed_now,
        uuid_factory=UUIDSequence(3800),
    )
    source_id = _registry(workspace_root)["sources"][0]["source_id"]
    before = tree_snapshot(input_root)
    source.chmod(stat.S_IREAD)
    read_only_mode = stat.S_IMODE(source.stat().st_mode)
    try:
        result = run_single_choice_parse(
            input_root=input_root,
            workspace_root=workspace_root,
            source_id=source_id,
            now=fixed_now,
            uuid_factory=UUIDSequence(3900),
        )
        assert result.status == "complete"
        assert tree_snapshot(input_root) == before
        assert stat.S_IMODE(source.stat().st_mode) == read_only_mode
    finally:
        source.chmod(stat.S_IREAD | stat.S_IWRITE)


def test_source_symlink_replacement_is_rejected_where_supported(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "input"
    workspace_root = tmp_path / "workspace"
    external_root = tmp_path / "external"
    input_root.mkdir()
    external_root.mkdir()
    source = input_root / "synthetic.txt"
    payload = (
        "1. [single_choice] Synthetic replacement?\n- A. Yes\n- B. No\n"
    ).encode()
    source.write_bytes(payload)
    external = external_root / "synthetic.txt"
    external.write_bytes(payload)
    run_inventory(
        input_root=input_root,
        workspace_root=workspace_root,
        now=fixed_now,
        uuid_factory=UUIDSequence(4000),
    )
    source_id = _registry(workspace_root)["sources"][0]["source_id"]
    source.unlink()
    try:
        source.symlink_to(external)
    except (NotImplementedError, OSError) as error:
        pytest.skip(
            "symbolic link replacement unavailable: "
            f"{type(error).__name__}"
        )
    before = tree_snapshot(workspace_root)

    with pytest.raises(SourceResolutionError, match="path is unsafe"):
        run_single_choice_parse(
            input_root=input_root,
            workspace_root=workspace_root,
            source_id=source_id,
            now=fixed_now,
            uuid_factory=_unexpected_uuid,
        )

    assert tree_snapshot(workspace_root) == before
