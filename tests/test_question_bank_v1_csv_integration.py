from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

from qbbank.serialization import read_question_bank_json
from qbproduction.csv_exporter import serialize_standard_question_bank_csv
from qbproduction.csv_projection import project_question_items_to_csv_rows


GOLDEN_PATH = Path(__file__).parent / "expected" / "qbbank-v1" / "question-bank.json"


def test_canonical_questions_are_existing_standard_csv_exporter_upstream() -> None:
    bank = read_question_bank_json(GOLDEN_PATH)

    csv_text = serialize_standard_question_bank_csv(
        project_question_items_to_csv_rows(bank.questions)
    )
    records = list(csv.DictReader(StringIO(csv_text)))

    assert list(records[0]) == [
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
    ]
    assert [record["题型"] for record in records] == ["单选题", "多选题", "判断题"]
    assert records[0]["正确答案"] == ""
    assert records[1]["正确答案"] == "AC"
    assert records[2]["正确答案"] == "正确"
    assert records[2]["A"] == records[2]["B"] == ""
    assert all("source_id" not in record for record in records)
