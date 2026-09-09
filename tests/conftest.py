from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "curate-question-bank"
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
EXPECTED_ROOT = REPOSITORY_ROOT / "tests" / "expected" / "golden-course"

sys.path.insert(0, str(SCRIPTS_ROOT))


def load_expected(name: str) -> dict:
    return json.loads((EXPECTED_ROOT / name).read_text(encoding="utf-8"))


def expected_bundle(validated: bool = False) -> dict:
    manifest = load_expected("manifest.json")
    candidates = load_expected("candidates.json")
    if validated:
        validated_ids = set(load_expected("validated-after-decisions.json")["validated_candidate_ids"])
        candidates = deepcopy(candidates)
        for candidate in candidates["candidates"]:
            if candidate["candidate_id"] in validated_ids:
                candidate["status"] = "validated"
    reviews = load_expected("review-queue.json")
    decisions = load_expected("decisions.json")
    return {
        "manifest": manifest,
        "candidates": candidates["candidates"],
        "review_items": reviews["review_items"],
        "decisions": decisions["decisions"],
    }
