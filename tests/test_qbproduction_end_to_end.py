from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

from m2_helpers import UUIDSequence
from qbproduction.pipeline import build_standard_question_bank_csv


TEST_ROOT = Path(__file__).parent
SOURCE_FIXTURE = TEST_ROOT / "fixtures" / "qbproduction-end-to-end" / "questions.md"
GOLDEN_CSV = (
    TEST_ROOT
    / "expected"
    / "qbproduction-end-to-end"
    / "standard-question-bank.csv"
)
SOURCE_ID = "41000000-0000-4000-8000-000000000001"


def _build() -> str:
    return build_standard_question_bank_csv(
        SOURCE_FIXTURE.read_text(encoding="utf-8"),
        source_id=SOURCE_ID,
        uuid_factory=UUIDSequence(4200),
    )


def test_real_parser_to_standard_csv_matches_exact_golden_bytes() -> None:
    csv_text = _build()

    assert csv_text.encode("utf-8") == GOLDEN_CSV.read_bytes()
    assert _build() == csv_text


def test_end_to_end_csv_has_exact_public_contract_and_no_internal_leak() -> None:
    csv_text = _build()
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
    assert [record["全局序号"] for record in records] == ["1", "2"]
    assert records[0]["E"] == "Epsilon"
    assert records[1]["D"] == records[1]["E"] == ""
    assert all(record["试卷/章节"] == "" for record in records)
    assert all(record["正确答案"] == "" for record in records)
    assert all(record["解析"] == "" for record in records)
    assert SOURCE_ID not in csv_text
    assert "source_option_id" not in csv_text
    assert "candidate" not in csv_text
