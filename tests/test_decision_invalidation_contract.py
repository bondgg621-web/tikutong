from __future__ import annotations

import copy

from conftest import SKILL_ROOT, expected_bundle
from qbcore.validation import validate_bundle


def test_validated_candidate_requires_a_current_valid_answer_decision() -> None:
    bundle = expected_bundle(validated=True)
    assert validate_bundle(bundle) == []
    bundle["decisions"][0]["status"] = "needs_revalidation"
    errors = validate_bundle(bundle)
    assert any(error.code == "QB-VALIDATED-GATE-FAILED" for error in errors)


def test_runtime_rejects_decision_bound_to_a_stale_candidate_revision() -> None:
    bundle = expected_bundle()
    bundle["decisions"][0]["candidate_revision"] = 99
    errors = validate_bundle(bundle)
    assert any(error.code == "QB-DECISION-REVISION-STALE" for error in errors)


def test_runtime_rejects_nonexistent_evidence_source() -> None:
    bundle = expected_bundle()
    bundle["decisions"][0]["evidence"][0]["source_id"] = "90000000-0000-4000-8000-000000000009"
    errors = validate_bundle(bundle)
    assert any(error.code == "QB-EVIDENCE-REFERENCE-MISSING" for error in errors)


def test_true_false_contract_uses_normalized_boolean_and_source_lexeme() -> None:
    bundle = expected_bundle()
    candidate = copy.deepcopy(bundle["candidates"][0])
    candidate.update(
        candidate_id="71000000-0000-4000-8000-000000000007",
        question_type="true_false",
        options=[],
    )
    bundle["candidates"].append(candidate)
    decision = copy.deepcopy(bundle["decisions"][0])
    decision.update(
        decision_id="81000000-0000-4000-8000-000000000008",
        candidate_id=candidate["candidate_id"],
        value={"boolean_value": True, "source_lexeme": "对"},
    )
    bundle["decisions"].append(decision)
    assert validate_bundle(bundle) == []


def test_state_contract_freezes_the_decision_invalidation_matrix() -> None:
    contract = (SKILL_ROOT / "references" / "state-contract.md").read_text(encoding="utf-8")
    for text in ("needs_revalidation", "QB-IDENTITY-AMBIGUOUS", "历史决定归档"):
        assert text in contract
