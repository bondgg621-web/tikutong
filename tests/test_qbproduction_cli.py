from __future__ import annotations

import csv
from io import StringIO
import os
from pathlib import Path
import socket
import sys

from conftest import SCRIPTS_ROOT
from m2_helpers import run_subprocess
from qbproduction.cli import main


TEST_ROOT = Path(__file__).parent
SOURCE_FIXTURE = TEST_ROOT / "fixtures" / "qbproduction-end-to-end" / "questions.md"
GOLDEN_CSV = (
    TEST_ROOT
    / "expected"
    / "qbproduction-end-to-end"
    / "standard-question-bank.csv"
)


def _run(*args: object):
    existing = os.environ.get("PYTHONPATH")
    pythonpath = str(SCRIPTS_ROOT)
    if existing:
        pythonpath = os.pathsep.join((pythonpath, existing))
    return run_subprocess(
        (sys.executable, "-m", "qbproduction", *map(str, args)),
        env={"PYTHONPATH": pythonpath},
    )


def test_help_succeeds() -> None:
    completed = _run("--help")

    assert completed.returncode == 0
    assert "--input" in completed.stdout
    assert "--output" in completed.stdout
    assert completed.stderr == ""


def test_real_file_cli_output_matches_task11_golden_and_is_deterministic(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"

    completed_first = _run("--input", SOURCE_FIXTURE, "--output", first)
    completed_second = _run("--input", SOURCE_FIXTURE, "--output", second)

    assert completed_first.returncode == completed_second.returncode == 0
    assert completed_first.stderr == completed_second.stderr == ""
    assert first.read_bytes() == second.read_bytes() == GOLDEN_CSV.read_bytes()
    records = list(csv.DictReader(StringIO(first.read_text(encoding="utf-8"))))
    assert all(record["正确答案"] == "" for record in records)
    assert "source_option_id" not in first.read_text(encoding="utf-8")
    assert "candidate_id" not in first.read_text(encoding="utf-8")


def test_missing_input_fails_closed_without_output(tmp_path: Path) -> None:
    output = tmp_path / "output.csv"

    completed = _run(
        "--input",
        tmp_path / "missing.md",
        "--output",
        output,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert completed.stderr == "error: input file does not exist\n"
    assert not output.exists()
    assert "Traceback" not in completed.stderr


def test_non_file_and_unsupported_input_fail_closed(tmp_path: Path) -> None:
    output = tmp_path / "output.csv"
    unsupported = tmp_path / "questions.pdf"
    unsupported.write_text("synthetic", encoding="utf-8")

    directory_result = _run("--input", tmp_path, "--output", output)
    unsupported_result = _run("--input", unsupported, "--output", output)

    assert directory_result.returncode == 2
    assert directory_result.stderr == "error: input must be a regular file\n"
    assert unsupported_result.returncode == 2
    assert unsupported_result.stderr == "error: unsupported input type\n"
    assert not output.exists()


def test_unpublishable_source_preserves_existing_output(tmp_path: Path) -> None:
    source = tmp_path / "invalid.md"
    source.write_text("not a strict question", encoding="utf-8")
    output = tmp_path / "output.csv"
    output.write_bytes(b"PREVIOUS-COMPLETE-OUTPUT")

    completed = _run("--input", source, "--output", output)

    assert completed.returncode == 3
    assert completed.stdout == ""
    assert completed.stderr.startswith("error: source text must contain publishable")
    assert "Traceback" not in completed.stderr
    assert output.read_bytes() == b"PREVIOUS-COMPLETE-OUTPUT"


def test_missing_output_parent_returns_output_error(tmp_path: Path) -> None:
    output = tmp_path / "missing-parent" / "output.csv"

    completed = _run("--input", SOURCE_FIXTURE, "--output", output)

    assert completed.returncode == 4
    assert completed.stdout == ""
    assert completed.stderr == "error: output parent does not exist\n"
    assert not output.exists()


def test_atomic_replace_failure_preserves_previous_output_and_cleans_temp(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    output = tmp_path / "output.csv"
    output.write_bytes(b"PREVIOUS-COMPLETE-OUTPUT")

    def fail_replace(_source: object, _target: object) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr("qbproduction.cli.os.replace", fail_replace)
    exit_code = main(["--input", str(SOURCE_FIXTURE), "--output", str(output)])
    captured = capsys.readouterr()

    assert exit_code == 4
    assert captured.out == ""
    assert captured.err == "error: could not publish output CSV\n"
    assert output.read_bytes() == b"PREVIOUS-COMPLETE-OUTPUT"
    assert list(tmp_path.glob(".*.tmp")) == []


def test_cli_does_not_attempt_network_access(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    def fail_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network attempted")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    output = tmp_path / "output.csv"

    exit_code = main(["--input", str(SOURCE_FIXTURE), "--output", str(output)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "standard question bank CSV written\n"
    assert captured.err == ""
    assert output.read_bytes() == GOLDEN_CSV.read_bytes()
