from __future__ import annotations

from copy import deepcopy

from m1_helpers import UUIDSequence, fixed_now
from qbcore.registry import reconcile_registry
from qbcore.workspace_contracts import validate_workspace_document


def inventory(*entries: tuple[str, str]) -> dict:
    return {"entries": [{"relative_path": path, "size_bytes": 1, "content_hash": content_hash, "support_status": "builtin_text"} for path, content_hash in entries]}


def empty_registry() -> dict:
    return {"schema_version": "1.0", "dataset_id": "00000000-0000-4000-8000-000000000100", "registry_revision": 0, "updated_at": "2026-08-12T00:00:00Z", "sources": []}


def test_first_scan_assigns_distinct_ids_at_revision_one() -> None:
    registry, issues = reconcile_registry(empty_registry(), inventory(("a.txt", "a" * 64), ("b.txt", "a" * 64)), uuid_factory=UUIDSequence(1), now=fixed_now)
    assert issues == []
    assert [source["revision"] for source in registry["sources"]] == [1, 1]
    assert len({source["source_id"] for source in registry["sources"]}) == 2
    assert validate_workspace_document("source-registry", registry) == []


def test_same_path_same_hash_keeps_identity_and_revision() -> None:
    first, _ = reconcile_registry(empty_registry(), inventory(("a.txt", "a" * 64)), uuid_factory=UUIDSequence(1), now=fixed_now)
    second, issues = reconcile_registry(first, inventory(("a.txt", "a" * 64)), uuid_factory=UUIDSequence(50), now=fixed_now)
    assert issues == []
    assert second["sources"][0]["source_id"] == first["sources"][0]["source_id"]
    assert second["sources"][0]["revision"] == 1
    assert validate_workspace_document("source-registry", second) == []


def first_registry(*entries: tuple[str, str]) -> dict:
    value, issues = reconcile_registry(empty_registry(), inventory(*entries), uuid_factory=UUIDSequence(1), now=fixed_now)
    assert issues == []
    return value


def test_same_path_changed_hash_increments_source_revision() -> None:
    old = first_registry(("a.txt", "a" * 64))
    source_id = old["sources"][0]["source_id"]
    new, issues = reconcile_registry(old, inventory(("a.txt", "b" * 64)), uuid_factory=UUIDSequence(50), now=fixed_now)
    assert issues == []
    assert new["sources"][0]["source_id"] == source_id
    assert new["sources"][0]["revision"] == 2
    assert validate_workspace_document("source-registry", new) == []


def test_unique_content_hash_rename_preserves_identity_and_revision() -> None:
    old = first_registry(("old.txt", "a" * 64))
    new, issues = reconcile_registry(old, inventory(("new.txt", "a" * 64)), uuid_factory=UUIDSequence(50), now=fixed_now)
    assert issues == []
    assert new["sources"][0]["source_id"] == old["sources"][0]["source_id"]
    assert new["sources"][0]["revision"] == 1
    assert new["sources"][0]["path_history"] == ["old.txt", "new.txt"]
    assert validate_workspace_document("source-registry", new) == []


def test_one_old_to_two_new_same_hash_is_ambiguous_and_does_not_migrate() -> None:
    old = first_registry(("old.txt", "a" * 64))
    old_id = old["sources"][0]["source_id"]
    new, issues = reconcile_registry(old, inventory(("one.txt", "a" * 64), ("two.txt", "a" * 64)), uuid_factory=UUIDSequence(50), now=fixed_now)
    assert [issue["code"] for issue in issues] == ["QB-IDENTITY-AMBIGUOUS"]
    by_id = {source["source_id"]: source for source in new["sources"]}
    assert by_id[old_id]["presence"] == "missing"
    assert all(by_id[source_id]["revision"] == 1 for source_id in by_id if source_id != old_id)
    assert validate_workspace_document("source-registry", new) == []


def test_two_old_to_one_new_same_hash_is_ambiguous_and_does_not_migrate() -> None:
    old = first_registry(("a.txt", "a" * 64), ("b.txt", "a" * 64))
    old_ids = {source["source_id"] for source in old["sources"]}
    new, issues = reconcile_registry(old, inventory(("c.txt", "a" * 64)), uuid_factory=UUIDSequence(50), now=fixed_now)
    assert [issue["code"] for issue in issues] == ["QB-IDENTITY-AMBIGUOUS"]
    assert all(source["presence"] == "missing" for source in new["sources"] if source["source_id"] in old_ids)
    assert next(source for source in new["sources"] if source["current_relative_path"] == "c.txt")["source_id"] not in old_ids
    assert validate_workspace_document("source-registry", new) == []


def test_path_and_content_change_create_new_identity_and_archive_old_as_missing() -> None:
    old = first_registry(("old.txt", "a" * 64))
    old_id = old["sources"][0]["source_id"]
    old_copy = deepcopy(old)
    discovery = inventory(("new.txt", "b" * 64))
    discovery_copy = deepcopy(discovery)
    new, issues = reconcile_registry(old, discovery, uuid_factory=UUIDSequence(50), now=fixed_now)
    assert issues == []
    assert old == old_copy and discovery == discovery_copy
    assert next(source for source in new["sources"] if source["source_id"] == old_id)["presence"] == "missing"
    assert next(source for source in new["sources"] if source["current_relative_path"] == "new.txt")["source_id"] != old_id
    assert validate_workspace_document("source-registry", new) == []
