from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime
from uuid import UUID

from qbcore.capabilities import _utc_z


def reconcile_registry(
    previous: dict,
    discovery: dict,
    *,
    uuid_factory: Callable[[], UUID],
    now: Callable[[], datetime],
) -> tuple[dict, list[dict]]:
    """Return new file identities without mutating either input."""
    old_sources = deepcopy(previous["sources"])
    new_entries = [deepcopy(entry) for entry in discovery["entries"] if entry["support_status"] != "read_failed"]
    old_paths = [source["current_relative_path"] for source in old_sources]
    new_paths = [entry["relative_path"] for entry in new_entries]
    if len(set(old_paths)) != len(old_paths):
        raise ValueError("source registry contains duplicate current paths")
    if len(set(new_paths)) != len(new_paths):
        raise ValueError("discovery inventory contains duplicate paths")

    old_unmatched = set(range(len(old_sources)))
    new_unmatched = set(range(len(new_entries)))
    reconciled: dict[int, dict] = {}
    issues: list[dict] = []
    old_by_path = {source["current_relative_path"]: index for index, source in enumerate(old_sources)}

    for new_index, entry in enumerate(new_entries):
        old_index = old_by_path.get(entry["relative_path"])
        if old_index is None:
            continue
        source = deepcopy(old_sources[old_index])
        if source["current_content_hash"] != entry["content_hash"]:
            source["current_content_hash"] = entry["content_hash"]
            source["revision"] += 1
        source["presence"] = "present"
        reconciled[old_index] = source
        old_unmatched.remove(old_index)
        new_unmatched.remove(new_index)

    old_by_hash: dict[str, list[int]] = defaultdict(list)
    new_by_hash: dict[str, list[int]] = defaultdict(list)
    for old_index in sorted(old_unmatched):
        old_by_hash[old_sources[old_index]["current_content_hash"]].append(old_index)
    for new_index in sorted(new_unmatched):
        new_by_hash[new_entries[new_index]["content_hash"]].append(new_index)

    for content_hash in sorted(set(old_by_hash) & set(new_by_hash)):
        old_group = old_by_hash[content_hash]
        new_group = new_by_hash[content_hash]
        if len(old_group) == 1 and len(new_group) == 1:
            old_index, new_index = old_group[0], new_group[0]
            source = deepcopy(old_sources[old_index])
            new_path = new_entries[new_index]["relative_path"]
            source["current_relative_path"] = new_path
            if source["path_history"][-1] != new_path:
                source["path_history"].append(new_path)
            source["presence"] = "present"
            reconciled[old_index] = source
            old_unmatched.remove(old_index)
            new_unmatched.remove(new_index)
            continue
        issues.append({
            "code": "QB-IDENTITY-AMBIGUOUS",
            "summary": "content hash does not establish a unique one-to-one rename",
            "relative_paths": sorted([old_sources[index]["current_relative_path"] for index in old_group] + [new_entries[index]["relative_path"] for index in new_group], key=lambda value: (value.casefold(), value)),
            "source_ids": sorted(old_sources[index]["source_id"] for index in old_group),
        })

    result_sources = list(reconciled.values())
    for old_index in sorted(old_unmatched):
        source = deepcopy(old_sources[old_index])
        source["presence"] = "missing"
        result_sources.append(source)
    for new_index in sorted(new_unmatched):
        entry = new_entries[new_index]
        result_sources.append({"source_id": str(uuid_factory()), "current_relative_path": entry["relative_path"], "path_history": [entry["relative_path"]], "current_content_hash": entry["content_hash"], "revision": 1, "presence": "present"})

    result_sources.sort(key=lambda source: (source["current_relative_path"].casefold(), source["source_id"]))
    previous_sorted = sorted(deepcopy(previous["sources"]), key=lambda source: (source["current_relative_path"].casefold(), source["source_id"]))
    changed = result_sources != previous_sorted
    return ({"schema_version": "1.0", "dataset_id": previous["dataset_id"], "registry_revision": previous["registry_revision"] + (1 if changed else 0), "updated_at": _utc_z(now()) if changed else previous["updated_at"], "sources": result_sources}, issues)
