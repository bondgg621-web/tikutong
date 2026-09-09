from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

from qbproduction.csv_exporter import (
    serialize_standard_question_bank_csv,
    write_standard_question_bank_csv,
)
from qbproduction.csv_projection import (
    STANDARD_QUESTION_BANK_CSV_HEADER,
    project_question_items_to_csv_rows,
)
from qbproduction.question_item import QuestionItem


def _item() -> QuestionItem:
    return QuestionItem(
        question_id="internal-question-id",
        question_revision=1,
        question_type="single_choice",
        stem='A stem with comma, "quote", and\nnewline',
        options=[
            {
                "label": "A",
                "text": 'Option, "A"\ncontinued',
                "source_option_id": "34000000-0000-4000-8000-000000000001",
            }
        ],
        source_reference={"private": "source-do-not-export"},
        status="validated",
        metadata={"private": "metadata-do-not-export"},
        answer="A",
        explanation='Explanation, with "quote" and\nnewline',
    )


def test_csv_text_round_trips_quoted_multiline_fields_without_internal_leaks() -> None:
    rows = project_question_items_to_csv_rows([_item()])

    text = serialize_standard_question_bank_csv(rows)
    reader = csv.DictReader(StringIO(text))
    records = list(reader)

    assert tuple(reader.fieldnames or ()) == STANDARD_QUESTION_BANK_CSV_HEADER
    assert records == [
        {
            "全局序号": "1",
            "试卷/章节": "",
            "题型": "单选题",
            "题干": 'A stem with comma, "quote", and\nnewline',
            "A": 'Option, "A"\ncontinued',
            "B": "",
            "C": "",
            "D": "",
            "E": "",
            "正确答案": "A",
            "解析": 'Explanation, with "quote" and\nnewline',
        }
    ]
    for private_value in (
        "internal-question-id",
        "34000000-0000-4000-8000-000000000001",
        "source-do-not-export",
        "metadata-do-not-export",
        "validated",
    ):
        assert private_value not in text


def test_file_export_is_utf8_without_bom_and_round_trips(tmp_path: Path) -> None:
    output = tmp_path / "question-bank.csv"
    rows = project_question_items_to_csv_rows([_item(), _item()])

    write_standard_question_bank_csv(rows, output)

    raw = output.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    decoded = raw.decode("utf-8")
    records = list(csv.reader(StringIO(decoded)))
    assert records[0] == list(STANDARD_QUESTION_BANK_CSV_HEADER)
    assert [record[0] for record in records[1:]] == ["1", "2"]
