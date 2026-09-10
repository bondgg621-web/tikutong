from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
import re

from qbproduction.csv_exporter import serialize_standard_question_bank_csv
from qbproduction.csv_projection import (
    STANDARD_QUESTION_BANK_CSV_HEADER,
    StandardQuestionBankRow,
)


ROOT = Path(__file__).resolve().parents[1]
PREVIEW_PATH = ROOT / "tools" / "preview" / "index.html"
PREVIEW_README_PATH = ROOT / "tools" / "preview" / "README.md"
TRIAL_CSV_PATH = (
    ROOT / "examples" / "user-trial" / "expected-standard-question-bank.csv"
)
PUBLIC_PREVIEW_DOCS = (
    ROOT / "README.md",
    ROOT / "docs" / "USER_TRIAL.md",
    ROOT / "examples" / "user-trial" / "EXPECTED_RESULTS.md",
    ROOT / ".github" / "ISSUE_TEMPLATE" / "own-bank-trial.md",
    PREVIEW_PATH,
    PREVIEW_README_PATH,
)


def _load_rows() -> tuple[str, list[dict[str, str]]]:
    text = TRIAL_CSV_PATH.read_text(encoding="utf-8")
    return text, list(csv.DictReader(text.splitlines(keepends=True)))


def test_preview_public_files_exist() -> None:
    assert PREVIEW_PATH.is_file()
    assert PREVIEW_README_PATH.is_file()
    assert TRIAL_CSV_PATH.is_file()


def test_standard_trial_csv_is_exact_current_exporter_output() -> None:
    text, source_rows = _load_rows()
    reader = csv.DictReader(text.splitlines(keepends=True))

    assert tuple(reader.fieldnames or ()) == STANDARD_QUESTION_BANK_CSV_HEADER
    rows = [
        StandardQuestionBankRow(
            sequence_number=int(row["全局序号"]),
            paper_or_chapter=row["试卷/章节"],
            question_type=row["题型"],
            stem=row["题干"],
            option_a=row["A"],
            option_b=row["B"],
            option_c=row["C"],
            option_d=row["D"],
            option_e=row["E"],
            correct_answer=row["正确答案"],
            explanation=row["解析"],
        )
        for row in source_rows
    ]
    assert serialize_standard_question_bank_csv(rows) == text


def test_standard_trial_csv_locks_counts_and_answers() -> None:
    _, rows = _load_rows()

    assert len(rows) == 12
    assert Counter(row["题型"] for row in rows) == {
        "单选题": 5,
        "多选题": 4,
        "判断题": 3,
    }
    assert [row["正确答案"] for row in rows] == [
        "B",
        "E",
        "A",
        "",
        "ABE",
        "ACE",
        "ACE",
        "",
        "正确",
        "错误",
        "",
        "B",
    ]


def test_public_preview_material_has_no_legacy_paths_or_answer_filling_rules() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in PUBLIC_PREVIEW_DOCS)

    assert re.search(r"C:\\Users\\|D:\\下载(?:\\|\b)|/Users/|/home/", combined) is None
    for forbidden in (
        "D:\\下载",
        "quiz_tool",
        "不得留空",
        "自动查资料补答案",
        "每题必须有解析",
        "AI 出题",
    ):
        assert forbidden not in combined
    assert "题库内容在浏览器本地处理" in combined
