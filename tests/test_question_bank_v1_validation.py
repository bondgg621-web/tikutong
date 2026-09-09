from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from qbbank.validation import QuestionBankValidationError, validate_question_bank_mapping


GOLDEN_PATH = Path(__file__).parent / "expected" / "qbbank-v1" / "question-bank.json"


def _bank() -> dict:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def _reject(bank: dict, message: str) -> None:
    with pytest.raises(QuestionBankValidationError, match=message):
        validate_question_bank_mapping(bank)


def test_minimal_multi_source_mixed_bank_is_valid() -> None:
    validate_question_bank_mapping(_bank())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", "1.1", "schema_version"),
        ("bank_id", "not-a-uuid", "bank_id"),
        ("title", "", "title"),
        ("questions", [], "questions"),
        ("sources", [], "sources"),
    ],
)
def test_rejects_invalid_top_level_contract(field: str, value: object, message: str) -> None:
    bank = _bank()
    bank[field] = value
    _reject(bank, message)


def test_rejects_duplicate_and_invalid_source_ids() -> None:
    bank = _bank()
    bank["sources"].append(deepcopy(bank["sources"][0]))
    _reject(bank, "duplicate source_id")

    bank = _bank()
    bank["sources"][0]["source_id"] = "invalid"
    _reject(bank, "source_id")


@pytest.mark.parametrize("source_file", [r"C:\questions.pdf", "/questions.pdf"])
def test_rejects_obvious_absolute_source_paths(source_file: str) -> None:
    bank = _bank()
    bank["sources"][0]["source_file"] = source_file
    _reject(bank, "source_file")


def test_rejects_unknown_source_reference_and_empty_locator() -> None:
    bank = _bank()
    bank["questions"][0]["source_reference"]["source_id"] = (
        "52000000-0000-4000-8000-000000000099"
    )
    _reject(bank, "unknown source_id")

    bank = _bank()
    bank["questions"][0]["source_reference"]["locator"] = ""
    _reject(bank, "locator")


def test_rejects_invalid_and_duplicate_question_ids() -> None:
    bank = _bank()
    bank["questions"][0]["question_id"] = "invalid"
    _reject(bank, "question_id")

    bank = _bank()
    bank["questions"][1]["question_id"] = bank["questions"][0]["question_id"]
    _reject(bank, "duplicate question_id")


def test_rejects_invalid_choice_labels_and_duplicates() -> None:
    bank = _bank()
    bank["questions"][0]["options"][0]["label"] = "F"
    _reject(bank, "option label")

    bank = _bank()
    bank["questions"][0]["options"][1]["label"] = "A"
    _reject(bank, "duplicate option label")


def test_rejects_duplicate_source_option_id_within_question() -> None:
    bank = _bank()
    first, second = bank["questions"][0]["options"]
    second["source_option_id"] = first["source_option_id"]
    _reject(bank, "duplicate source_option_id")


def test_rejects_invalid_question_type_and_true_false_options() -> None:
    bank = _bank()
    bank["questions"][0]["question_type"] = "essay"
    _reject(bank, "question_type")

    bank = _bank()
    bank["questions"][2]["options"] = [deepcopy(bank["questions"][0]["options"][0])]
    _reject(bank, "true_false")


def test_rejects_unknown_bank_source_question_and_option_fields() -> None:
    bank = _bank()
    bank["assets"] = []
    _reject(bank, "unknown field")

    bank = _bank()
    bank["sources"][0]["revision"] = 1
    _reject(bank, "unknown field")

    bank = _bank()
    bank["questions"][0]["new_contract"] = True
    _reject(bank, "unknown field")

    bank = _bank()
    bank["questions"][0]["options"][0]["media_ref"] = "asset-1"
    _reject(bank, "unknown field")
