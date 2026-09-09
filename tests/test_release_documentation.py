from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from qbassist import ExtractedQuestionBatch, build_question_bank_from_extracted
from qbbank import SourceRecord, write_question_bank_json
from qbproduction.csv_exporter import write_standard_question_bank_csv
from qbproduction.csv_projection import project_question_items_to_csv_rows


ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
SKILL_PATH = ROOT / "skills" / "curate-question-bank" / "SKILL.md"
ASSISTED_GUIDE_PATH = (
    ROOT
    / "skills"
    / "curate-question-bank"
    / "references"
    / "assisted-intake-v1.md"
)
SCRIPTS_PATH = ROOT / "skills" / "curate-question-bank" / "scripts"
SCHEMA_HASHES = {
    "question-bank-v1.schema.json": "0a4ba89909bc814743ce26ecd44362cc7df32e8084356018d2a124dad9380dee",
    "extracted-question-v1.schema.json": "3fa111c8fcff818727b731e5dae1f9c10f4451c752a1c3a0e3adc25a3ea29c2d",
    "question-item.schema.json": "948f2d998fc956a86b3cb0267ea71d0b03b75f7914643683977e6dcec3bede3c",
}


def test_readme_has_release_sections_and_plain_language_positioning() -> None:
    text = README_PATH.read_text(encoding="utf-8")

    for heading in (
        "# 题库通 TikuTong",
        "## What TikuTong is",
        "## What TikuTong is not",
        "## Installation",
        "## Quick Start",
        "## Supported inputs",
        "## Supported question types",
        "## Outputs",
        "## Example",
        "## Privacy and local-first boundary",
        "## Current limitations",
    ):
        assert heading in text
    assert "Agent-native Question Bank Compiler" in text
    assert "Turn existing questions from local documents into structured, portable question banks." in text
    assert "把散落在本地 PDF、Word、图片和文本中的已有题目，整理成结构化、可迁移的标准题库。" in text
    assert "agent-native local question-bank compiler for existing questions" in text
    assert "AI quiz generator" in text
    assert "QuestionBank v1.0" in text
    assert "全局序号,试卷/章节,题型,题干,A,B,C,D,E,正确答案,解析" in text


def test_readme_install_and_commands_match_the_real_public_api_boundary() -> None:
    text = README_PATH.read_text(encoding="utf-8")

    assert "Python 3.12" in text
    assert "skills/curate-question-bank/scripts" in text
    assert "python -m qbproduction --input" in text
    assert "pip install qbc" not in text.casefold()
    assert SCRIPTS_PATH.is_dir()
    assert callable(ExtractedQuestionBatch.from_dict)
    assert callable(build_question_bank_from_extracted)
    assert callable(write_question_bank_json)
    assert callable(project_question_items_to_csv_rows)
    assert callable(write_standard_question_bank_csv)


def test_skill_routes_deterministic_and_assisted_work_without_internal_history() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")

    assert "# 题库通 TikuTong" in text
    assert "Agent-native Question Bank Compiler" in text
    assert "## Choose a route" in text
    assert "### Route A — Deterministic" in text
    assert "### Route B — Assisted" in text
    assert "references/assisted-intake-v1.md" in text
    assert "ExtractedQuestion" in text
    assert "QuestionBank v1.0" in text
    assert "qbc_extraction_notes" in ASSISTED_GUIDE_PATH.read_text(encoding="utf-8")


def test_documentation_draws_the_environment_and_product_capability_boundary() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    skill = SKILL_PATH.read_text(encoding="utf-8")
    combined = readme + "\n" + skill

    for required in (
        "Agent environment can read",
        "no bundled PDF or DOCX parser",
        "no bundled OCR",
        "no bundled LLM client",
        "does not guarantee that the user's Agent is offline",
        "multiple_choice",
        "true_false",
        "options=[]",
    ):
        assert required in combined
    for forbidden in (
        "QBC parses PDF",
        "QBC parses DOCX",
        "QBC performs OCR",
        "QBC supports only single-choice questions",
        "QBC is always offline",
    ):
        assert forbidden.casefold() not in combined.casefold()


def test_frozen_contract_schemas_remain_byte_exact() -> None:
    schema_root = ROOT / "skills" / "curate-question-bank" / "schemas"

    assert {
        name: sha256((schema_root / name).read_bytes()).hexdigest()
        for name in SCHEMA_HASHES
    } == SCHEMA_HASHES
