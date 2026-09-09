from __future__ import annotations

from copy import deepcopy
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "curate-question-bank" / "scripts"))

from qbproduction.question_item_materializer import (
    QuestionItemMaterializationError,
    materialize_question_item,
)
from qbcore.single_choice_parser import ParsedOption, ParsedSingleChoice


CANDIDATE_ID = "21000000-0000-4000-8000-000000000001"
SOURCE_ID = "11000000-0000-4000-8000-000000000001"
OPTION_A_ID = "31000000-0000-4000-8000-000000000001"
OPTION_B_ID = "31000000-0000-4000-8000-000000000002"


def parsed_question() -> ParsedSingleChoice:
    return ParsedSingleChoice(
        display_number="1",
        stem="Example",
        header_line=10,
        options=(
            ParsedOption(source_label="A", text="Alpha", line=11),
            ParsedOption(source_label="B", text="Beta", line=12),
        ),
    )


def candidate() -> dict:
    return {
        "candidate_id": CANDIDATE_ID,
        "candidate_revision": 2,
        "source_id": SOURCE_ID,
        "locator": "line:10",
        "question_type": "single_choice",
        "status": "validated",
        "stem": "Example",
        "options": [
            {
                "option_id": OPTION_A_ID,
                "candidate_id": CANDIDATE_ID,
                "current_position": 1,
                "source_label": "A",
                "source_ref": {"source_id": SOURCE_ID, "locator": "line:11"},
            },
            {
                "option_id": OPTION_B_ID,
                "candidate_id": CANDIDATE_ID,
                "current_position": 2,
                "source_label": "B",
                "source_ref": {"source_id": SOURCE_ID, "locator": "line:12"},
            },
        ],
    }


def test_materializer_combines_parsed_text_with_persistent_candidate_identity() -> None:
    item = materialize_question_item(parsed_question(), candidate())

    assert item.question_id == CANDIDATE_ID
    assert item.question_revision == 2
    assert item.stem == "Example"
    assert item.source_reference == {"source_id": SOURCE_ID, "locator": "line:10"}
    assert item.options == [
        {"label": "A", "text": "Alpha", "source_option_id": OPTION_A_ID},
        {"label": "B", "text": "Beta", "source_option_id": OPTION_B_ID},
    ]
    schema_path = (
        Path(__file__).resolve().parents[1]
        / "skills"
        / "curate-question-bank"
        / "schemas"
        / "question-item.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert list(Draft7Validator(schema).iter_errors(item.to_dict())) == []


def test_materializer_matches_by_explicit_identity_fields_not_array_order() -> None:
    value = candidate()
    value["options"].reverse()

    item = materialize_question_item(parsed_question(), value)

    assert [option["source_option_id"] for option in item.options] == [OPTION_A_ID, OPTION_B_ID]


@pytest.mark.parametrize(
    ("mutate", "expected_message"),
    [
        (lambda value: value.update(stem="Different"), "stem"),
        (lambda value: value["options"][0].update(source_label="B"), "correspond"),
        (lambda value: value["options"][0].update(current_position=2), "correspond"),
        (lambda value: value["options"][0]["source_ref"].update(locator="line:99"), "correspond"),
        (lambda value: value["options"][0]["source_ref"].update(source_id="12000000-0000-4000-8000-000000000001"), "source_id"),
        (lambda value: value["options"][0].update(candidate_id="22000000-0000-4000-8000-000000000001"), "candidate_id"),
        (lambda value: value["options"][1].update(option_id=OPTION_A_ID), "option_id"),
    ],
)
def test_materializer_fails_closed_when_pairing_is_not_exact(mutate, expected_message: str) -> None:
    value = deepcopy(candidate())
    mutate(value)

    with pytest.raises(QuestionItemMaterializationError, match=expected_message):
        materialize_question_item(parsed_question(), value)
