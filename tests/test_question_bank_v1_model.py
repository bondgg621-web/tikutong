from __future__ import annotations

import json
from pathlib import Path

from qbbank.question_bank import QuestionBank, SourceRecord
from qbproduction.question_item import QuestionItem


GOLDEN_PATH = Path(__file__).parent / "expected" / "qbbank-v1" / "question-bank.json"


def test_model_loads_multi_source_mixed_question_bank_without_new_question_type() -> None:
    raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))

    bank = QuestionBank.from_dict(raw)

    assert bank.schema_version == "1.0"
    assert bank.title == "神经病学标准题库"
    assert all(type(source) is SourceRecord for source in bank.sources)
    assert all(type(question) is QuestionItem for question in bank.questions)
    assert [source.source_type for source in bank.sources] == ["pdf", "markdown"]
    assert [question.question_type for question in bank.questions] == [
        "single_choice",
        "multiple_choice",
        "true_false",
    ]
    assert bank.questions[0].answer is None
    assert bank.questions[2].options == []
    assert bank.to_dict() == raw


def test_model_preserves_first_materialization_bank_identity() -> None:
    raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))

    bank = QuestionBank.from_dict(raw)

    assert bank.bank_id == raw["bank_id"]
    assert bank.to_dict()["bank_id"] == raw["bank_id"]
