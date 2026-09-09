from __future__ import annotations

import json
from pathlib import Path

from qbassist.compiler import build_question_bank_from_extracted
from qbassist.extracted_question import ExtractedQuestionBatch
from qbbank.question_bank import SourceRecord
from qbbank.serialization import deserialize_question_bank, serialize_question_bank


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "qbassist-v1" / "extracted-questions.json"
GOLDEN_PATH = ROOT / "tests" / "expected" / "qbassist-v1" / "question-bank.json"
IDS = iter(
    (
        "71000000-0000-4000-8000-000000000001",
        "72000000-0000-4000-8000-000000000001",
        "73000000-0000-4000-8000-000000000001",
        "73000000-0000-4000-8000-000000000002",
        "72000000-0000-4000-8000-000000000002",
        "73000000-0000-4000-8000-000000000003",
        "73000000-0000-4000-8000-000000000004",
        "73000000-0000-4000-8000-000000000005",
        "72000000-0000-4000-8000-000000000003",
    )
)


def _bank():
    return build_question_bank_from_extracted(
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
        uuid_factory=lambda: next(IDS),
    )


def test_compiler_matches_hand_authored_canonical_golden_and_round_trips() -> None:
    golden_text = GOLDEN_PATH.read_text(encoding="utf-8")

    serialized = serialize_question_bank(_bank())
    restored = deserialize_question_bank(serialized)

    assert serialized == golden_text
    assert restored.to_dict() == json.loads(golden_text)
    assert [item.source_reference["source_id"] for item in restored.questions] == [
        "61000000-0000-4000-8000-000000000001",
        "61000000-0000-4000-8000-000000000001",
        "61000000-0000-4000-8000-000000000002",
    ]
