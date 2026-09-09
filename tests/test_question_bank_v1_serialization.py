from __future__ import annotations

from pathlib import Path

from qbbank.question_bank import QuestionBank
from qbbank.serialization import (
    deserialize_question_bank,
    read_question_bank_json,
    serialize_question_bank,
    write_question_bank_json,
)


GOLDEN_PATH = Path(__file__).parent / "expected" / "qbbank-v1" / "question-bank.json"


def test_serialization_is_deterministic_utf8_readable_and_matches_golden() -> None:
    golden_text = GOLDEN_PATH.read_text(encoding="utf-8")
    bank = deserialize_question_bank(golden_text)

    first = serialize_question_bank(bank)
    second = serialize_question_bank(bank)

    assert first == second == golden_text
    assert first.endswith("\n")
    assert "神经病学标准题库" in first
    assert "\\u795e" not in first


def test_round_trip_preserves_bank_question_source_and_option_order() -> None:
    original = deserialize_question_bank(GOLDEN_PATH.read_text(encoding="utf-8"))

    restored = deserialize_question_bank(serialize_question_bank(original))

    assert restored == original
    assert [item.question_id for item in restored.questions] == [
        item.question_id for item in original.questions
    ]
    assert [item.source_id for item in restored.sources] == [
        item.source_id for item in original.sources
    ]
    assert [option["source_option_id"] for option in restored.questions[1].options] == [
        option["source_option_id"] for option in original.questions[1].options
    ]


def test_file_api_writes_and_reads_single_utf8_json_file(tmp_path: Path) -> None:
    bank = QuestionBank.from_dict(__import__("json").loads(GOLDEN_PATH.read_text(encoding="utf-8")))
    output = tmp_path / "canonical-bank.json"

    write_question_bank_json(bank, output)

    assert output.read_bytes() == GOLDEN_PATH.read_bytes()
    assert read_question_bank_json(output) == bank
