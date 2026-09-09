from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import UUID

import pytest

from conftest import REPOSITORY_ROOT
from m2_helpers import UUIDSequence, bootstrap_m1_workspace, fixed_now
from qbcore.cli import main


ENTRYPOINT = (
    REPOSITORY_ROOT
    / "skills"
    / "curate-question-bank"
    / "scripts"
    / "curate_question_bank.py"
)


def _arguments(bootstrapped) -> list[str]:
    return [
        "parse-single-choice",
        "--input-root",
        str(bootstrapped.input_root),
        "--workspace-root",
        str(bootstrapped.workspace_root),
        "--source-id",
        bootstrapped.registry["sources"][0]["source_id"],
    ]


@pytest.mark.parametrize(
    "missing_flag",
    ("--input-root", "--workspace-root", "--source-id"),
)
def test_parse_command_requires_all_explicit_inputs(
    tmp_path: Path,
    missing_flag: str,
) -> None:
    bootstrapped = bootstrap_m1_workspace(
        tmp_path,
        fixture_names=("strict-two.txt",),
    )

    arguments = _arguments(bootstrapped)
    index = arguments.index(missing_flag)
    del arguments[index : index + 2]
    with pytest.raises(SystemExit) as raised:
        main(arguments)

    assert raised.value.code == 2


def test_parse_command_complete_returns_stable_json_and_exit_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bootstrapped = bootstrap_m1_workspace(
        tmp_path,
        fixture_names=("strict-two.txt",),
    )
    sequence = UUIDSequence(2000)
    monkeypatch.setattr("qbcore.cli.system_uuid", sequence)
    monkeypatch.setattr("qbcore.cli.system_now", fixed_now)

    exit_code = main(_arguments(bootstrapped))

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    expected_run_id = str(UUID(int=2000, version=4))
    assert captured.out == json.dumps(
        {"run_id": expected_run_id, "status": "complete"},
        sort_keys=True,
    ) + "\n"
    assert payload == {"run_id": expected_run_id, "status": "complete"}
    assert captured.err == ""


def test_parse_command_needs_review_returns_exit_three(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bootstrapped = bootstrap_m1_workspace(
        tmp_path,
        fixture_names=("malformed.md",),
    )
    monkeypatch.setattr("qbcore.cli.system_uuid", UUIDSequence(2100))
    monkeypatch.setattr("qbcore.cli.system_now", fixed_now)

    exit_code = main(_arguments(bootstrapped))

    captured = capsys.readouterr()
    assert exit_code == 3
    assert json.loads(captured.out)["status"] == "needs_review"
    assert captured.err == ""


def test_parse_command_existing_candidate_fails_without_source_or_path_leakage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bootstrapped = bootstrap_m1_workspace(
        tmp_path,
        fixture_names=("strict-two.txt",),
    )
    monkeypatch.setattr("qbcore.cli.system_uuid", UUIDSequence(2200))
    monkeypatch.setattr("qbcore.cli.system_now", fixed_now)
    assert main(_arguments(bootstrapped)) == 0
    capsys.readouterr()

    exit_code = main(_arguments(bootstrapped))

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "already has a candidate artifact" in captured.err
    assert "Synthetic" not in captured.err
    assert "Alpha" not in captured.err
    assert str(tmp_path) not in captured.err


@pytest.mark.parametrize(
    "source_id",
    ("not-a-uuid", "00000000-0000-4000-8000-00000000000A"),
)
def test_parse_command_rejects_noncanonical_source_uuid(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    source_id: str,
) -> None:
    bootstrapped = bootstrap_m1_workspace(
        tmp_path,
        fixture_names=("strict-two.txt",),
    )
    arguments = _arguments(bootstrapped)
    arguments[-1] = source_id

    assert main(arguments) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "lowercase UUID" in captured.err
    assert str(tmp_path) not in captured.err


def test_parse_command_sanitizes_unexpected_runtime_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bootstrapped = bootstrap_m1_workspace(
        tmp_path,
        fixture_names=("strict-two.txt",),
    )
    monkeypatch.setattr(
        "qbcore.cli.run_single_choice_parse",
        lambda **_kwargs: (_ for _ in ()).throw(
            OSError(str(tmp_path / "private" / "workspace.json"))
        ),
    )

    assert main(_arguments(bootstrapped)) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: operation failed\n"
    assert str(tmp_path) not in captured.err


@pytest.mark.parametrize("exception_type", (TypeError, KeyError))
def test_parse_command_sanitizes_all_unexpected_exceptions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    exception_type: type[Exception],
) -> None:
    bootstrapped = bootstrap_m1_workspace(
        tmp_path,
        fixture_names=("strict-two.txt",),
    )
    private_path = tmp_path / "private" / "workspace.json"
    monkeypatch.setattr(
        "qbcore.cli.run_single_choice_parse",
        lambda **_kwargs: (_ for _ in ()).throw(exception_type(str(private_path))),
    )

    assert main(_arguments(bootstrapped)) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: operation failed\n"
    assert str(tmp_path) not in captured.err


def test_parse_command_sanitizes_invalid_argument_echo(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bootstrapped = bootstrap_m1_workspace(
        tmp_path,
        fixture_names=("strict-two.txt",),
    )
    private_path = tmp_path / "private" / "workspace.json"

    with pytest.raises(SystemExit) as raised:
        main([*_arguments(bootstrapped), "--private-path", str(private_path)])

    captured = capsys.readouterr()
    assert raised.value.code == 2
    assert captured.out == ""
    assert captured.err == "error: invalid arguments\n"
    assert str(tmp_path) not in captured.err


def test_parse_command_runs_through_real_subprocess(tmp_path: Path) -> None:
    bootstrapped = bootstrap_m1_workspace(
        tmp_path,
        fixture_names=("strict-two.txt",),
    )
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    completed = subprocess.run(
        [sys.executable, str(ENTRYPOINT), *_arguments(bootstrapped)],
        cwd=REPOSITORY_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    payload = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert payload["status"] == "complete"
    assert completed.stderr == ""
