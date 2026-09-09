from __future__ import annotations

import json
from pathlib import Path

from qbassist.compiler import build_question_bank_from_extracted
from qbassist.extracted_question import ExtractedQuestionBatch
from qbbank.question_bank import SourceRecord
from qbproduction.csv_exporter import serialize_standard_question_bank_csv
from qbproduction.csv_projection import project_question_items_to_csv_rows


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "qbassist-v1" / "extracted-questions.json"
EXPECTED_PATH = ROOT / "tests" / "expected" / "qbassist-v1" / "standard-question-bank.csv"


def test_assisted_intake_reuses_existing_standard_csv_projection_and_exporter() -> None:
    ids = iter(
        f"74000000-0000-4000-8000-{index:012d}"
        for index in range(1, 10)
    )
    bank = build_question_bank_from_extracted(
        title="辅助抽取神经病学题库",
        sources=[
            SourceRecord(
                "61000000-0000-4000-8000-000000000001",
                "神经病学题库.pdf",
                "pdf",
            ),
            SourceRecord(
                "61000000-0000-4000-8000-000000000002",
                "扫描判断题.png",
                "image",
            ),
        ],
        batch=ExtractedQuestionBatch.from_dict(
            json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        ),
        uuid_factory=lambda: next(ids),
    )

    actual = serialize_standard_question_bank_csv(
        project_question_items_to_csv_rows(bank.questions)
    )

    assert actual == EXPECTED_PATH.read_text(encoding="utf-8")
