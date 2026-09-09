"""Minimal local CLI for Standard Question Bank CSV production."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile
from typing import Sequence
from uuid import uuid4

from .pipeline import build_standard_question_bank_csv


SUCCESS = 0
INPUT_ERROR = 2
PIPELINE_ERROR = 3
OUTPUT_ERROR = 4
SUPPORTED_INPUT_SUFFIXES = frozenset({".md", ".markdown", ".txt"})


class ProductionInputError(ValueError):
    """Raised for invalid or unreadable explicitly selected input."""


class ProductionOutputError(ValueError):
    """Raised when the requested output cannot be published safely."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qbproduction",
        description="Build a Standard Question Bank CSV from one local text file.",
    )
    parser.add_argument("--input", required=True, help="local .txt/.md/.markdown file")
    parser.add_argument("--output", required=True, help="destination CSV file")
    return parser


def _read_input(path: Path) -> str:
    if not path.exists():
        raise ProductionInputError("input file does not exist")
    if path.is_symlink() or not path.is_file():
        raise ProductionInputError("input must be a regular file")
    if path.suffix.casefold() not in SUPPORTED_INPUT_SUFFIXES:
        raise ProductionInputError("unsupported input type")
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise ProductionInputError("could not read input file") from error
    try:
        return payload.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as error:
        raise ProductionInputError("input must be valid UTF-8 text") from error


def _absolute_key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def _validate_output(input_path: Path, output_path: Path) -> None:
    if _absolute_key(input_path) == _absolute_key(output_path):
        raise ProductionOutputError("output must differ from input")
    parent = output_path.parent
    if not parent.exists():
        raise ProductionOutputError("output parent does not exist")
    if parent.is_symlink() or not parent.is_dir():
        raise ProductionOutputError("output parent must be a regular directory")
    if output_path.exists() and (output_path.is_symlink() or not output_path.is_file()):
        raise ProductionOutputError("output must be a regular file path")


def _write_csv_atomic(output_path: Path, csv_text: str) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            dir=output_path.parent,
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(csv_text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, output_path)
        temporary_path = None
    except OSError as error:
        raise ProductionOutputError("could not publish output CSV") from error
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_path = Path(args.input)
    output_path = Path(args.output)

    try:
        source_text = _read_input(input_path)
    except ProductionInputError as error:
        print(f"error: {error}", file=sys.stderr)
        return INPUT_ERROR

    try:
        _validate_output(input_path, output_path)
    except ProductionOutputError as error:
        print(f"error: {error}", file=sys.stderr)
        return OUTPUT_ERROR

    try:
        csv_text = build_standard_question_bank_csv(
            source_text,
            source_id=str(uuid4()),
            uuid_factory=uuid4,
        )
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return PIPELINE_ERROR

    try:
        _write_csv_atomic(output_path, csv_text)
    except ProductionOutputError as error:
        print(f"error: {error}", file=sys.stderr)
        return OUTPUT_ERROR

    print("standard question bank CSV written")
    return SUCCESS


__all__ = ["build_parser", "main"]
