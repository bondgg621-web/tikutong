from __future__ import annotations

import copy

from conftest import expected_bundle, load_expected
from qbcore.validation import validate_bundle


def test_option_identity_is_distinct_from_current_label_and_position() -> None:
    candidate = load_expected("candidates.json")["candidates"][0]
    option = candidate["options"][0]
    assert option["option_id"] != option["source_label"]
    assert option["current_position"] == 1
    assert option["previous_labels"] == []


def test_runtime_rejects_resolved_option_id_that_does_not_exist() -> None:
    bundle = expected_bundle()
    bundle["decisions"][0]["value"]["resolved_option_ids"] = ["99999999-0000-4000-8000-000000000099"]
    errors = validate_bundle(bundle)
    assert any(error.code == "QB-OPTION-REFERENCE-MISSING" for error in errors)


def test_runtime_rejects_option_owned_by_another_candidate() -> None:
    bundle = expected_bundle()
    foreign_option = bundle["candidates"][1]["options"][0]["option_id"]
    bundle["decisions"][0]["value"]["resolved_option_ids"] = [foreign_option]
    errors = validate_bundle(bundle)
    assert any(error.code == "QB-OPTION-OWNERSHIP-INVALID" for error in errors)


def test_multiple_choice_requires_two_distinct_owned_options() -> None:
    bundle = expected_bundle()
    candidate = copy.deepcopy(bundle["candidates"][0])
    candidate["candidate_id"] = "70000000-0000-4000-8000-000000000007"
    candidate["question_type"] = "multiple_choice"
    candidate["status"] = "candidate"
    bundle["candidates"].append(candidate)
    decision = copy.deepcopy(bundle["decisions"][0])
    decision["decision_id"] = "80000000-0000-4000-8000-000000000008"
    decision["candidate_id"] = candidate["candidate_id"]
    decision["value"]["resolved_option_ids"] = [candidate["options"][0]["option_id"]]
    bundle["decisions"].append(decision)
    errors = validate_bundle(bundle)
    assert any(error.code == "QB-ANSWER-CARDINALITY-INVALID" for error in errors)


def test_duplicate_or_changed_option_text_requires_review_not_automatic_migration() -> None:
    contract = load_expected("review-queue.json")["review_items"]
    assert any(item["issue_code"] == "QB-OPTION-IDENTITY-AMBIGUOUS" for item in contract)


def test_identity_contract_freezes_reorder_and_answer_target_outcomes() -> None:
    from conftest import SKILL_ROOT

    contract = (SKILL_ROOT / "references" / "identity-contract.md").read_text(encoding="utf-8")
    for required_case in (
        "唯一选项文字重排",
        "重排后答案仍指向原 option ID",
        "重排后答案指向另一 option ID",
        "选项文字修改",
    ):
        assert required_case in contract
