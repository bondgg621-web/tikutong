from __future__ import annotations

from dataclasses import fields
import json
from pathlib import Path

from qbassist.extracted_question import (
    ExtractedOption,
    ExtractedQuestion,
    ExtractedQuestionBatch,
    ExtractedSourceReference,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "qbassist-v1" / "extracted-questions.json"


def test_model_loads_natural_external_answer_representations_and_preserves_order() -> None:
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    batch = ExtractedQuestionBatch.from_dict(raw)

    assert all(type(item) is ExtractedQuestion for item in batch.questions)
    assert all(type(option) is ExtractedOption for option in batch.questions[0].options)
    assert type(batch.questions[0].source_reference) is ExtractedSourceReference
    assert [item.question_type for item in batch.questions] == [
        "single_choice",
        "multiple_choice",
        "true_false",
    ]
    assert batch.questions[0].answer is None
    assert batch.questions[1].answer == ["A", "C"]
    assert batch.questions[2].answer is False
    assert [option.label for option in batch.questions[1].options] == ["A", "B", "C"]
    assert batch.to_dict() == raw


def test_extracted_question_model_contains_no_qbc_owned_identity_fields() -> None:
    names = {field.name for field in fields(ExtractedQuestion)}

    assert names == {
        "question_type",
        "stem",
        "options",
        "answer",
        "explanation",
        "chapter",
        "source_reference",
        "extraction_notes",
    }
    assert {
        "question_id",
        "source_option_id",
        "candidate_id",
        "revision",
        "fingerprint",
    }.isdisjoint(names)
