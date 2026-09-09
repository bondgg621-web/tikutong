from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from uuid import UUID

import pytest

from qbassist.compiler import AssistedIntakeCompilationError, build_question_bank_from_extracted
from qbassist.extracted_question import (
    ExtractedQuestionBatch,
    ExtractedQuestionValidationError,
)
from qbbank.question_bank import SourceRecord


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "qbassist-v1" / "extracted-questions.json"
DETERMINISTIC_IDS = (
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


def _payload() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _sources() -> list[SourceRecord]:
    return [
        SourceRecord(
            source_id="61000000-0000-4000-8000-000000000001",
            source_file="神经病学题库.pdf",
            source_type="pdf",
        ),
        SourceRecord(
            source_id="61000000-0000-4000-8000-000000000002",
            source_file="扫描判断题.png",
            source_type="image",
        ),
    ]


def _deterministic_factory():
    values = iter(DETERMINISTIC_IDS)
    return lambda: next(values)


def _compile(payload: dict | None = None):
    return build_question_bank_from_extracted(
        title="辅助抽取神经病学题库",
        sources=_sources(),
        batch=ExtractedQuestionBatch.from_dict(payload or _payload()),
        uuid_factory=_deterministic_factory(),
    )


def _set(payload: dict, path: tuple[object, ...], value: object) -> None:
    target: object = payload
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    target[path[-1]] = value  # type: ignore[index]


def test_compiler_owns_identity_status_revision_and_preserves_content_order() -> None:
    bank = _compile()

    assert bank.bank_id == DETERMINISTIC_IDS[0]
    assert [item.question_id for item in bank.questions] == [
        DETERMINISTIC_IDS[1],
        DETERMINISTIC_IDS[4],
        DETERMINISTIC_IDS[8],
    ]
    assert [item.question_revision for item in bank.questions] == [1, 1, 1]
    assert [item.status for item in bank.questions] == ["candidate"] * 3
    assert [option["source_option_id"] for option in bank.questions[1].options] == list(
        DETERMINISTIC_IDS[5:8]
    )
    assert [item.stem for item in bank.questions] == [
        "正常成人视力通常记录为？",
        "下列哪些属于脑神经？",
        "周围神经属于中枢神经系统。",
    ]
    assert [option["label"] for option in bank.questions[1].options] == ["A", "B", "C"]
    assert bank.questions[0].answer is None
    assert bank.questions[1].answer == ["A", "C"]
    assert bank.questions[2].answer is False
    assert bank.questions[0].metadata == {
        "qbc_extraction_notes": "原扫描件答案标记不清晰。"
    }
    assert bank.questions[1].metadata is None


def test_production_factory_generates_unique_uuid4_identity_without_true_false_options() -> None:
    bank = build_question_bank_from_extracted(
        title="辅助抽取神经病学题库",
        sources=_sources(),
        batch=ExtractedQuestionBatch.from_dict(_payload()),
    )
    generated = [bank.bank_id]
    generated.extend(item.question_id for item in bank.questions)
    generated.extend(
        option["source_option_id"]
        for item in bank.questions
        for option in item.options
    )

    assert len(generated) == len(set(generated))
    assert all(UUID(value).version == 4 for value in generated)
    assert bank.questions[2].options == []


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("questions", 0, "question_type"), "essay", "question_type"),
        (("questions", 0, "stem"), "", "stem"),
        (("questions", 0, "options"), [{"label": "A", "text": "only"}], "2-5"),
        (
            ("questions", 0, "options"),
            [{"label": "A", "text": "x"}] * 6,
            "2-5",
        ),
        (("questions", 0, "options", 1, "label"), "A", "duplicate option label"),
        (("questions", 0, "options", 1, "label"), "F", "option label"),
        (("questions", 0, "options", 1, "text"), "", "option text"),
        (("questions", 0, "answer"), "E", "answer"),
        (("questions", 1, "answer"), ["A", "A"], "duplicate"),
        (("questions", 1, "answer"), ["A", "E"], "answer"),
        (("questions", 1, "answer"), ["A"], "at least two"),
        (
            ("questions", 2, "options"),
            [{"label": "A", "text": "incorrect synthetic option"}],
            "true_false",
        ),
        (("questions", 2, "answer"), "false", "boolean"),
        (("questions", 0, "source_reference", "locator"), "", "locator"),
    ],
)
def test_extraction_validation_rejects_invalid_content(
    path: tuple[object, ...], value: object, message: str
) -> None:
    payload = _payload()
    _set(payload, path, value)

    with pytest.raises(ExtractedQuestionValidationError, match=message):
        ExtractedQuestionBatch.from_dict(payload)


@pytest.mark.parametrize(
    ("container_path", "field"),
    [
        (("questions", 0), "question_id"),
        (("questions", 0), "candidate_id"),
        (("questions", 0), "revision"),
        (("questions", 0), "fingerprint"),
        (("questions", 0), "duplicate_group"),
        (("questions", 0, "options", 0), "option_id"),
        (("questions", 0, "options", 0), "source_option_id"),
    ],
)
def test_extraction_rejects_codex_supplied_internal_fields(
    container_path: tuple[object, ...], field: str
) -> None:
    payload = _payload()
    target: object = payload
    for key in container_path:
        target = target[key]  # type: ignore[index]
    target[field] = "forbidden"  # type: ignore[index]

    with pytest.raises(ExtractedQuestionValidationError, match=field):
        ExtractedQuestionBatch.from_dict(payload)


def test_empty_batch_and_unknown_fields_fail_closed() -> None:
    with pytest.raises(ExtractedQuestionValidationError, match="non-empty"):
        ExtractedQuestionBatch.from_dict({"questions": []})

    payload = _payload()
    payload["unexpected"] = True
    with pytest.raises(ExtractedQuestionValidationError, match="unexpected"):
        ExtractedQuestionBatch.from_dict(payload)


def test_compiler_rejects_unknown_source_without_consuming_or_repairing_it() -> None:
    payload = _payload()
    payload["questions"][0]["source_reference"]["source_id"] = (
        "61000000-0000-4000-8000-000000000099"
    )

    with pytest.raises(AssistedIntakeCompilationError, match="unknown source_id"):
        _compile(payload)


def test_true_and_null_answers_are_preserved_without_inference() -> None:
    payload = _payload()
    payload["questions"][2]["answer"] = True

    bank = _compile(payload)

    assert bank.questions[0].answer is None
    assert bank.questions[2].answer is True


def test_invalid_or_repeated_injected_uuid_fails_closed() -> None:
    with pytest.raises(AssistedIntakeCompilationError, match="UUID4"):
        build_question_bank_from_extracted(
            title="辅助抽取神经病学题库",
            sources=_sources(),
            batch=ExtractedQuestionBatch.from_dict(_payload()),
            uuid_factory=lambda: "not-a-uuid",
        )

    repeated = lambda: "71000000-0000-4000-8000-000000000001"
    with pytest.raises(AssistedIntakeCompilationError, match="duplicate"):
        build_question_bank_from_extracted(
            title="辅助抽取神经病学题库",
            sources=_sources(),
            batch=ExtractedQuestionBatch.from_dict(_payload()),
            uuid_factory=repeated,
        )
