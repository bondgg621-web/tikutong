from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from m2_helpers import UUIDSequence
from qbcore.candidate_materializer import materialize_candidates
from qbcore.single_choice_parser import parse_single_choice
from qbproduction.batch_assembly import (
    BatchQuestionItemAssemblyError,
    assemble_question_items,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "qbproduction-end-to-end"
    / "questions.md"
)
SOURCE_ID = "41000000-0000-4000-8000-000000000001"


def _parsed_and_candidates():
    result = parse_single_choice(FIXTURE.read_text(encoding="utf-8"))
    assert result.publishable
    document = materialize_candidates(
        result.questions,
        source_id=SOURCE_ID,
        uuid_factory=UUIDSequence(4200),
    )
    return result.questions, document["candidates"]


def test_batch_assembly_pairs_by_locator_and_preserves_parsed_order() -> None:
    parsed, candidates = _parsed_and_candidates()
    candidate_by_locator = {candidate["locator"]: candidate for candidate in candidates}

    items = assemble_question_items(reversed(parsed), reversed(candidates))

    assert [item.stem for item in items] == [question.stem for question in reversed(parsed)]
    for parsed_question, item in zip(reversed(parsed), items, strict=True):
        candidate = candidate_by_locator[f"line:{parsed_question.header_line}"]
        assert item.question_id == candidate["candidate_id"]
        assert [option["text"] for option in item.options] == [
            option.text for option in parsed_question.options
        ]
        assert [option["source_option_id"] for option in item.options] == [
            option["option_id"] for option in candidate["options"]
        ]


def test_missing_candidate_fails_closed() -> None:
    parsed, candidates = _parsed_and_candidates()

    with pytest.raises(BatchQuestionItemAssemblyError, match="missing Candidate"):
        assemble_question_items(parsed, candidates[:-1])


def test_candidate_without_parsed_question_fails_closed() -> None:
    parsed, candidates = _parsed_and_candidates()

    with pytest.raises(BatchQuestionItemAssemblyError, match="missing ParsedSingleChoice"):
        assemble_question_items(parsed[:-1], candidates)


def test_duplicate_candidate_locator_is_ambiguous_and_fails_closed() -> None:
    parsed, candidates = _parsed_and_candidates()
    duplicate = deepcopy(candidates[0])
    duplicate["candidate_id"] = "43000000-0000-4000-8000-000000000001"

    with pytest.raises(BatchQuestionItemAssemblyError, match="duplicate Candidate locator"):
        assemble_question_items(parsed, [*candidates, duplicate])


def test_duplicate_parsed_locator_is_ambiguous_and_fails_closed() -> None:
    parsed, candidates = _parsed_and_candidates()

    with pytest.raises(BatchQuestionItemAssemblyError, match="duplicate ParsedSingleChoice locator"):
        assemble_question_items([parsed[0], parsed[0]], candidates)
