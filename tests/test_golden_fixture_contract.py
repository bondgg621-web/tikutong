from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys

from conftest import EXPECTED_ROOT, REPOSITORY_ROOT, SKILL_ROOT, expected_bundle, load_expected
from qbcore.validation import schema_path, validate_bundle


def test_golden_course_contains_only_the_frozen_single_choice_fixture_scope() -> None:
    course = REPOSITORY_ROOT / "tests" / "fixtures" / "golden-course" / "course"
    assert {path.name for path in course.iterdir()} == {
        "chapter-1-questions.md",
        "chapter-1-answer.txt",
        "chapter-2-questions.md",
        "unrelated.txt",
        "duplicate-version.md",
    }
    questions = (course / "chapter-1-questions.md").read_text(encoding="utf-8")
    assert questions.count("single_choice") >= 7
    assert "missing answer" in questions
    assert "conflicting answer" in questions


def test_expected_artifacts_are_hand_authored_contract_samples_and_validate() -> None:
    assert {path.name for path in EXPECTED_ROOT.iterdir()} == {
        "manifest.json",
        "candidates.json",
        "review-queue.json",
        "decisions.json",
        "validated-after-decisions.json",
    }
    assert validate_bundle(expected_bundle()) == []
    assert validate_bundle(expected_bundle(validated=True)) == []


def test_expected_candidates_preserve_review_and_duplicate_option_cardinality() -> None:
    candidates = load_expected("candidates.json")["candidates"]
    assert [len(candidate["options"]) for candidate in candidates[:5]] == [4, 4, 4, 4, 4]
    assert len(candidates[5]["options"]) == len(candidates[6]["options"])


def test_all_runtime_schemas_live_inside_skill_package() -> None:
    assert schema_path("manifest.schema.json").parent == SKILL_ROOT / "schemas"
    assert not (REPOSITORY_ROOT / "schemas").exists()


def test_copied_skill_resolves_its_own_schema_without_repository_root(tmp_path) -> None:
    copied_skill = tmp_path / "curate-question-bank"
    shutil.copytree(SKILL_ROOT, copied_skill)
    script = (
        "import sys; "
        f"sys.path.insert(0, {str(copied_skill / 'scripts')!r}); "
        "from qbcore.validation import schema_path; "
        "print(schema_path('manifest.schema.json'))"
    )
    result = subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True)
    assert result.stdout.strip() == str(copied_skill / "schemas" / "manifest.schema.json")
