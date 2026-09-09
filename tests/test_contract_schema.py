from __future__ import annotations

import copy
import json

import jsonschema
import pytest
from referencing import Registry, Resource

from conftest import SKILL_ROOT, load_expected
from qbcore.validation import validate_document


SCHEMA_CASES = {
    "manifest": "manifest.schema.json",
    "run-state": "run-state.schema.json",
    "candidate": "candidate.schema.json",
    "review-item": "review-item.schema.json",
    "decision": "decision.schema.json",
    "question-bank-interchange": "question-bank-interchange.schema.json",
}


def _schema(name: str) -> dict:
    return json.loads((SKILL_ROOT / "schemas" / SCHEMA_CASES[name]).read_text(encoding="utf-8"))


def test_every_runtime_schema_is_a_valid_draft_2020_12_schema() -> None:
    for name in SCHEMA_CASES:
        jsonschema.Draft202012Validator.check_schema(_schema(name))


@pytest.mark.parametrize(
    ("mutate", "label"),
    [
        (lambda value: value["candidates"][0].pop("candidate_id"), "required"),
        (lambda value: value["candidates"][0].__setitem__("candidate_revision", "one"), "type"),
        (lambda value: value["candidates"][0].__setitem__("question_type", "essay"), "enum"),
        (lambda value: value["candidates"][0].__setitem__("candidate_id", "not-a-uuid"), "uuid"),
        (lambda value: value.__setitem__("candidates", []), "cardinality"),
    ],
)
def test_runtime_and_json_schema_reject_the_same_overlap_contract_errors(mutate, label: str) -> None:
    value = copy.deepcopy(load_expected("candidates.json"))
    mutate(value)
    runtime_errors = validate_document("candidate", value)
    assert runtime_errors, label
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(value, _schema("candidate"))


def test_runtime_schema_checks_do_not_require_jsonschema_at_runtime() -> None:
    valid = load_expected("candidates.json")
    assert validate_document("candidate", valid) == []


def test_interchange_schema_resolves_sibling_skill_schemas_from_portable_ids() -> None:
    registry = Registry()
    for filename in SCHEMA_CASES.values():
        schema = json.loads((SKILL_ROOT / "schemas" / filename).read_text(encoding="utf-8"))
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    manifest = load_expected("manifest.json")
    candidates = load_expected("candidates.json")
    reviews = load_expected("review-queue.json")
    decisions = load_expected("decisions.json")
    interchange = {"manifest": manifest, "candidates": candidates, "review_queue": reviews, "decisions": decisions}
    validator = jsonschema.Draft202012Validator(_schema("question-bank-interchange"), registry=registry)
    assert list(validator.iter_errors(interchange)) == []
