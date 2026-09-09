import json
from pathlib import Path


SCHEMA_PATH = (
    Path(__file__).parents[1]
    / "skills"
    / "curate-question-bank"
    / "schemas"
    / "question-item.schema.json"
)


REQUIRED_FIELDS = {
    "question_id",
    "question_revision",
    "question_type",
    "stem",
    "options",
    "source_reference",
    "status",
}


def test_question_item_schema_contract():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == REQUIRED_FIELDS
    assert schema["properties"]["question_revision"] == {
        "type": "integer",
        "minimum": 1,
    }


def test_question_item_options_preserve_candidate_option_identity():
    option_schema = schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))["properties"]["options"]["items"]

    assert option_schema["type"] == "object"
    assert option_schema["additionalProperties"] is False
    assert set(option_schema["required"]) == {"label", "text", "source_option_id"}
    assert option_schema["properties"]["label"]["type"] == "string"
    assert option_schema["properties"]["text"]["type"] == "string"
    assert option_schema["properties"]["source_option_id"] == {
        "type": "string",
        "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    }
