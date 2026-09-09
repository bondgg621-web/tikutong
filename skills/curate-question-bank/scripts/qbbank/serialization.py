"""Deterministic UTF-8 JSON serialization for canonical Question Bank v1.0."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .question_bank import QuestionBank
from .validation import QuestionBankValidationError, validate_question_bank


class QuestionBankSerializationError(ValueError):
    """Raised when canonical Question Bank JSON cannot be decoded."""


def serialize_question_bank(bank: QuestionBank) -> str:
    """Return deterministic, human-readable canonical JSON with one final newline."""

    validate_question_bank(bank)
    return json.dumps(bank.to_dict(), ensure_ascii=False, indent=2) + "\n"


def deserialize_question_bank(payload: str) -> QuestionBank:
    """Decode and validate one canonical Question Bank JSON document."""

    if not isinstance(payload, str):
        raise QuestionBankSerializationError("question bank JSON payload must be text")
    try:
        value: Any = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise QuestionBankSerializationError(f"invalid question bank JSON: {exc.msg}") from exc
    try:
        return QuestionBank.from_dict(value)
    except QuestionBankValidationError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise QuestionBankSerializationError("invalid question bank JSON value") from exc


def write_question_bank_json(bank: QuestionBank, path: str | Path) -> None:
    """Write one canonical UTF-8 JSON file without platform newline drift."""

    target = Path(path)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(serialize_question_bank(bank))


def read_question_bank_json(path: str | Path) -> QuestionBank:
    """Read one canonical UTF-8 JSON file."""

    return deserialize_question_bank(Path(path).read_text(encoding="utf-8"))
