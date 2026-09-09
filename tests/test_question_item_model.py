import sys
import json
from pathlib import Path

from jsonschema import Draft7Validator

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "curate-question-bank" / "scripts"))

from qbproduction.question_item import QuestionItem


OPTIONS = [
    {
        "label": "A",
        "text": "Alpha",
        "source_option_id": "31000000-0000-4000-8000-000000000001",
    },
    {
        "label": "B",
        "text": "Beta",
        "source_option_id": "31000000-0000-4000-8000-000000000002",
    },
]


def test_question_item_creation():
    item = QuestionItem(
        question_id="Q1",
        question_revision=1,
        question_type="single_choice",
        stem="Example",
        options=OPTIONS,
        source_reference={"source": "test"},
        status="draft",
    )

    assert item.question_id == "Q1"
    assert item.status == "draft"
    assert item.question_revision == 1
    assert item.options[1]["source_option_id"] == "31000000-0000-4000-8000-000000000002"


def test_question_item_serialization():
    item = QuestionItem(
        question_id="Q1",
        question_revision=1,
        question_type="single_choice",
        stem="Example",
        options=OPTIONS,
        source_reference={"source": "test"},
        status="draft",
    )

    data = item.to_dict()

    assert data["question_id"] == "Q1"
    assert data["options"] == OPTIONS
    assert data["options"] is not item.options
    assert {"chapter", "metadata", "answer", "explanation"}.isdisjoint(data)

    schema_path = (
        Path(__file__).resolve().parents[1]
        / "skills"
        / "curate-question-bank"
        / "schemas"
        / "question-item.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert list(Draft7Validator(schema).iter_errors(data)) == []
