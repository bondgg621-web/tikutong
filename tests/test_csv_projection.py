from __future__ import annotations

import pytest

from qbproduction.csv_projection import (
    STANDARD_QUESTION_BANK_CSV_HEADER,
    project_question_item_to_csv_row,
    project_question_items_to_csv_rows,
)
from qbproduction.question_item import QuestionItem


def _item(**overrides: object) -> QuestionItem:
    values: dict[str, object] = {
        "question_id": "Q-10",
        "question_revision": 1,
        "question_type": "single_choice",
        "stem": "Which option?",
        "options": [
            {
                "label": "C",
                "text": "Third",
                "source_option_id": "33000000-0000-4000-8000-000000000003",
            },
            {
                "label": "A",
                "text": "First",
                "source_option_id": "33000000-0000-4000-8000-000000000001",
            },
            {
                "label": "B",
                "text": "Second",
                "source_option_id": "33000000-0000-4000-8000-000000000002",
            },
        ],
        "source_reference": {"private": "source-do-not-export"},
        "status": "validated",
        "metadata": {"private": "metadata-do-not-export"},
    }
    values.update(overrides)
    return QuestionItem(**values)  # type: ignore[arg-type]


def test_header_and_single_choice_projection_are_exact() -> None:
    assert STANDARD_QUESTION_BANK_CSV_HEADER == (
        "全局序号",
        "试卷/章节",
        "题型",
        "题干",
        "A",
        "B",
        "C",
        "D",
        "E",
        "正确答案",
        "解析",
    )

    row = project_question_item_to_csv_row(_item(), sequence_number=7)

    assert row.to_dict() == {
        "全局序号": 7,
        "试卷/章节": "",
        "题型": "单选题",
        "题干": "Which option?",
        "A": "First",
        "B": "Second",
        "C": "Third",
        "D": "",
        "E": "",
        "正确答案": "",
        "解析": "",
    }


@pytest.mark.parametrize(
    ("question_type", "answer", "expected_type", "expected_answer"),
    [
        ("single_choice", " b ", "单选题", "B"),
        ("multiple_choice", ["C", "A"], "多选题", "AC"),
        ("multiple_choice", "C, A", "多选题", "AC"),
        ("true_false", True, "判断题", "正确"),
        ("true_false", "false", "判断题", "错误"),
    ],
)
def test_question_type_and_existing_answer_are_normalized(
    question_type: str,
    answer: object,
    expected_type: str,
    expected_answer: str,
) -> None:
    row = project_question_item_to_csv_row(
        _item(question_type=question_type, answer=answer),
        sequence_number=1,
    )

    assert row.question_type == expected_type
    assert row.correct_answer == expected_answer


def test_projection_preserves_present_chapter_and_explanation() -> None:
    row = project_question_item_to_csv_row(
        _item(chapter="Paper 1 / Chapter 2", explanation="Because A."),
        sequence_number=1,
    )

    assert row.paper_or_chapter == "Paper 1 / Chapter 2"
    assert row.explanation == "Because A."


def test_batch_sequence_is_one_based_and_internal_fields_do_not_leak() -> None:
    rows = project_question_items_to_csv_rows([_item(), _item(question_id="Q-11")])

    assert [row.sequence_number for row in rows] == [1, 2]
    assert set(rows[0].to_dict()) == set(STANDARD_QUESTION_BANK_CSV_HEADER)
    assert {
        "question_id",
        "source_option_id",
        "source_reference",
        "metadata",
        "status",
    }.isdisjoint(rows[0].to_dict())


def test_unknown_question_type_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported question_type"):
        project_question_item_to_csv_row(
            _item(question_type="essay"),
            sequence_number=1,
        )
