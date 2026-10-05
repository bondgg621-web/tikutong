"""Runtime-only IP-05B answer evidence and safe attachment tests."""

from __future__ import annotations

import pytest

from qbanswer.answer_parser import parse_answer_evidence, parse_answer_key_blocks
from qbanswer.association import associate_answer_evidence


SID = "00000000-0000-4000-8000-000000000001"


def _parse(text: str, **context):
    return parse_answer_evidence(
        text,
        source_id=SID,
        source_revision=1,
        **context,
    )


def _candidate(candidate_id: str, number: int, labels: tuple[str, ...] = ("A", "B", "C", "D")) -> dict:
    return {
        "candidate_id": candidate_id,
        "_question_number": number,
        "options": [
            {"source_label": label, "option_id": f"option-{candidate_id}-{label}"}
            for label in labels
        ],
    }


@pytest.mark.parametrize("text", ("1: A", "1.A", "1、A", "1）A", "1) A"))
def test_numbered_answer_variants(text: str) -> None:
    evidence = _parse(text)[0]

    assert evidence.answer_kind == "NUMBERED_ANSWER"
    assert evidence.question_number == 1
    assert evidence.normalized_labels == ("A",)
    assert evidence.locator == "line:1"


def test_inline_current_answer_requires_unique_context() -> None:
    attached = _parse(
        "答案：A",
        current_question_number=7,
        current_context_unique=True,
        structurally_adjacent=True,
        unresolved_boundary=False,
    )[0]
    uncertain = _parse("答案：A")[0]

    assert attached.answer_kind == "INLINE_CURRENT"
    assert attached.question_number == 7
    assert uncertain.answer_kind == "UNRESOLVED_ANSWER"
    assert "ANSWER_ATTACHMENT_UNCERTAIN" in uncertain.warnings


def test_inline_answer_ambiguous_not_attached() -> None:
    evidence = _parse(
        "正确答案：A",
        current_question_number=7,
        current_context_unique=False,
        structurally_adjacent=True,
    )[0]

    assert evidence.question_number is None
    assert evidence.answer_kind == "UNRESOLVED_ANSWER"
    assert "ANSWER_ATTACHMENT_UNCERTAIN" in evidence.warnings


@pytest.mark.parametrize("text", ("答案：ACD", "答案：A、C、D", "1: ACD"))
def test_multiselect_answer_labels(text: str) -> None:
    evidence = _parse(text)[0]

    assert evidence.normalized_labels == ("A", "C", "D")
    assert evidence.raw_answer in {"ACD", "A、C、D"}


def test_answer_key_block_and_entries_map_independently() -> None:
    blocks = parse_answer_key_blocks("1.A 2.B 3.C", source_id=SID)
    evidence = _parse("1.A 2.B 3.C")

    assert len(blocks) == 1
    assert [(entry.question_number, entry.normalized_labels) for entry in blocks[0].entries] == [
        (1, ("A",)),
        (2, ("B",)),
        (3, ("C",)),
    ]
    assert [(item.question_number, item.answer_kind) for item in evidence] == [
        (1, "ANSWER_KEY_BLOCK"),
        (2, "ANSWER_KEY_BLOCK"),
        (3, "ANSWER_KEY_BLOCK"),
    ]


def test_answer_key_block_is_not_attached_to_last_question() -> None:
    evidence = _parse("1:A 2:C 3:B")
    decisions = associate_answer_evidence(
        [_candidate("c1", 1), _candidate("c2", 2), _candidate("c3", 3)],
        evidence,
    )

    assert [decision.question_number for decision in decisions] == [1, 2, 3]
    assert [decision.candidate_id for decision in decisions] == ["c1", "c2", "c3"]


def test_text_answer_preserved_runtime_only() -> None:
    evidence = _parse("答案：肾小球滤过")[0]

    assert evidence.answer_kind == "TEXT_ANSWER"
    assert evidence.raw_answer == "肾小球滤过"
    assert evidence.normalized_labels == ()


@pytest.mark.parametrize("text", ("答案：正确", "答案：错误", "答案：√", "答案：×"))
def test_judgment_answer_preserved_runtime_only(text: str) -> None:
    evidence = _parse(text)[0]

    assert evidence.answer_kind == "JUDGMENT_ANSWER"
    assert evidence.normalized_labels == ()


def test_unknown_question_number_is_unresolved() -> None:
    decision = associate_answer_evidence([_candidate("c1", 1)], _parse("99: A"))[0]

    assert decision.decision == "UNRESOLVED"
    assert "QUESTION_NUMBER_UNRESOLVED" in decision.warnings


def test_unknown_option_label_is_unresolved() -> None:
    decision = associate_answer_evidence([_candidate("c1", 1, ("A", "B"))], _parse("1: D"))[0]

    assert decision.decision == "UNRESOLVED"
    assert "OPTION_LABEL_UNRESOLVED" in decision.warnings


def test_duplicate_conflicting_answer_is_not_attachable() -> None:
    decisions = associate_answer_evidence([_candidate("c1", 1)], _parse("1: A\n1: B"))

    assert all(decision.decision == "CONFLICT" for decision in decisions)
    assert all("ANSWER_CONFLICT" in decision.warnings for decision in decisions)


def test_duplicate_same_answer_remains_attachable() -> None:
    decisions = associate_answer_evidence([_candidate("c1", 1)], _parse("1: A\n1: A"))

    assert all(decision.decision == "ATTACHABLE" for decision in decisions)


def test_duplicate_question_number_is_low_confidence() -> None:
    decisions = associate_answer_evidence([_candidate("c1", 1), _candidate("c2", 1)], _parse("1: A"))

    assert decisions[0].decision == "UNRESOLVED"
    assert "DUPLICATE_QUESTION_NUMBER" in decisions[0].warnings


def test_answer_source_trace_is_preserved() -> None:
    evidence = _parse("\n1: A")[0]

    assert evidence.source_id == SID
    assert evidence.locator == "line:2"
    assert evidence.raw_text == "1: A"


def test_existing_m3_contract_shape_is_unchanged() -> None:
    evidence = _parse("1: A")[0]

    assert "as_dict" not in type(evidence).__dict__
