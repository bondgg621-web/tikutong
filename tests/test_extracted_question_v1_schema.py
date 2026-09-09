from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft7Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "skills" / "curate-question-bank" / "schemas" / "extracted-question-v1.schema.json"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "qbassist-v1" / "extracted-questions.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator() -> Draft7Validator:
    schema = _load(SCHEMA_PATH)
    Draft7Validator.check_schema(schema)
    return Draft7Validator(schema)


def test_schema_is_closed_batch_contract_without_qbc_owned_identity_fields() -> None:
    schema = _load(SCHEMA_PATH)
    question = schema["definitions"]["extracted_question"]
    option = schema["definitions"]["extracted_option"]

    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["questions"]
    assert schema["properties"]["questions"]["minItems"] == 1
    assert question["additionalProperties"] is False
    assert option["additionalProperties"] is False
    assert set(option["required"]) == {"label", "text"}
    for forbidden in (
        "question_id",
        "option_id",
        "source_option_id",
        "candidate_id",
        "revision",
        "fingerprint",
        "duplicate_group",
    ):
        assert forbidden not in question["properties"]
        assert forbidden not in option["properties"]


def test_hand_authored_mixed_fixture_validates() -> None:
    assert list(_validator().iter_errors(_load(FIXTURE_PATH))) == []


def test_schema_rejects_identity_fields_and_type_specific_answer_mismatches() -> None:
    payload = _load(FIXTURE_PATH)
    payload["questions"][0]["question_id"] = "not-codex-owned"
    assert list(_validator().iter_errors(payload))

    payload = _load(FIXTURE_PATH)
    payload["questions"][1]["answer"] = "AC"
    assert list(_validator().iter_errors(payload))

    payload = _load(FIXTURE_PATH)
    payload["questions"][2]["options"] = [
        deepcopy(payload["questions"][0]["options"][0])
    ]
    assert list(_validator().iter_errors(payload))
