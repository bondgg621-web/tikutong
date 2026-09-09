from __future__ import annotations

from conftest import SKILL_ROOT, expected_bundle, load_expected
from qbcore.validation import validate_bundle


def test_source_identity_uses_persistent_uuid_not_path_or_content_hash() -> None:
    manifest = load_expected("manifest.json")
    source = manifest["sources"][0]
    assert source["source_id"] != source["current_relative_path"]
    assert source["source_id"] != source["current_content_hash"]
    assert source["path_history"] == [source["current_relative_path"]]


def test_duplicate_content_candidates_keep_distinct_ids_and_are_not_merged() -> None:
    candidates = load_expected("candidates.json")["candidates"]
    duplicates = [item for item in candidates if item["duplicate_group"] == "dup-protocol"]
    assert len(duplicates) == 2
    assert len({item["candidate_id"] for item in duplicates}) == 2
    assert len({item["fingerprints"]["content_revision_fingerprint"] for item in duplicates}) == 1


def test_ambiguous_identity_has_a_review_item_and_no_inherited_decision() -> None:
    bundle = expected_bundle()
    ambiguous = [item for item in bundle["review_items"] if item["issue_code"] == "QB-IDENTITY-AMBIGUOUS"]
    assert len(ambiguous) == 1
    candidate_id = ambiguous[0]["candidate_id"]
    assert candidate_id not in {decision["candidate_id"] for decision in bundle["decisions"]}


def test_identity_reference_freezes_one_to_one_matching_and_fingerprint_limits() -> None:
    contract = (SKILL_ROOT / "references" / "identity-contract.md").read_text(encoding="utf-8")
    assert "Fingerprint 只是匹配证据，不是身份键" in contract
    assert "QB-IDENTITY-AMBIGUOUS" in contract
    assert "一对一" in contract


def test_identity_reference_covers_rename_locator_stem_and_duplicate_group_cases() -> None:
    contract = (SKILL_ROOT / "references" / "identity-contract.md").read_text(encoding="utf-8")
    for required_case in (
        "文件内容不变但重命名",
        "文件前方插题",
        "题干修改",
        "重复组之前插入普通题",
        "删除重复组中的一道题",
        "向重复组新增相同题",
    ):
        assert required_case in contract


def test_expected_candidate_bundle_respects_identity_references() -> None:
    assert validate_bundle(expected_bundle()) == []
