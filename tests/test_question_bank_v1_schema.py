from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "skills" / "curate-question-bank" / "schemas" / "question-bank-v1.schema.json"
QUESTION_ITEM_SCHEMA_PATH = ROOT / "skills" / "curate-question-bank" / "schemas" / "question-item.schema.json"
GOLDEN_PATH = ROOT / "tests" / "expected" / "qbbank-v1" / "question-bank.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator() -> Draft7Validator:
    schema = _load(SCHEMA_PATH)
    question_item_schema = _load(QUESTION_ITEM_SCHEMA_PATH)
    registry = Registry().with_resource(
        "question-item.schema.json",
        Resource.from_contents(question_item_schema),
    )
    return Draft7Validator(schema, registry=registry)


def test_question_bank_v1_schema_is_exact_and_reuses_question_item_schema() -> None:
    schema = _load(SCHEMA_PATH)
    Draft7Validator.check_schema(schema)

    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "schema_version",
        "bank_id",
        "title",
        "questions",
        "sources",
    }
    assert schema["properties"]["schema_version"] == {"const": "1.0"}
    assert schema["properties"]["questions"]["minItems"] == 1
    assert schema["properties"]["questions"]["items"] == {
        "$ref": "question-item.schema.json"
    }
    assert schema["properties"]["sources"]["minItems"] == 1
    assert set(schema["definitions"]["source_record"]["required"]) == {
        "source_id",
        "source_file",
        "source_type",
    }
    assert schema["definitions"]["source_record"]["additionalProperties"] is False
    assert schema["definitions"]["source_record"]["properties"]["source_type"]["enum"] == [
        "pdf",
        "docx",
        "image",
        "text",
        "markdown",
        "structured",
    ]


def test_hand_authored_golden_bank_validates_against_portable_schema_refs() -> None:
    assert list(_validator().iter_errors(_load(GOLDEN_PATH))) == []


def test_schema_rejects_unknown_bank_and_source_fields() -> None:
    bank = _load(GOLDEN_PATH)
    bank["bank_revision"] = 1
    assert list(_validator().iter_errors(bank))

    bank = _load(GOLDEN_PATH)
    bank["sources"][0]["content_sha256"] = "0" * 64
    assert list(_validator().iter_errors(bank))
