from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
GUIDE_PATH = ROOT / "docs" / "USER_TRIAL.md"
TRIAL_PATH = ROOT / "examples" / "user-trial" / "tikutong-standard-trial.md"
EXPECTED_PATH = ROOT / "examples" / "user-trial" / "EXPECTED_RESULTS.md"
ISSUE_TEMPLATE_PATH = (
    ROOT / ".github" / "ISSUE_TEMPLATE" / "own-bank-trial.md"
)


def test_public_trial_entry_and_files_exist() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    assert "## 🧪 Try TikuTong with your own question bank" in readme
    assert "[User Trial Guide](docs/USER_TRIAL.md)" in readme
    for path in (GUIDE_PATH, TRIAL_PATH, EXPECTED_PATH, ISSUE_TEMPLATE_PATH):
        assert path.is_file()


def test_standard_trial_has_questions_1_through_12_once() -> None:
    text = TRIAL_PATH.read_text(encoding="utf-8")
    question_numbers = [
        int(number) for number in re.findall(r"^### ([0-9]+)$", text, re.MULTILINE)
    ]

    assert question_numbers == list(range(1, 13))


def test_expected_results_lock_counts_answers_and_null_gates() -> None:
    text = EXPECTED_PATH.read_text(encoding="utf-8")

    for expected in (
        "Total: 12",
        "single_choice: 5",
        "multiple_choice: 4",
        "true_false: 3",
        "Q1 = B",
        "Q2 = E",
        "Q3 = A",
        "Q4 = null",
        "Q5 = ABE",
        "Q6 = ACE",
        "Q7 = ACE",
        "Q8 = null",
        "Q9 = true",
        "Q10 = false",
        "Q11 = null",
        "Q12 = B",
        "UNAUTHORIZED_ANSWER_INFERENCE=YES",
    ):
        assert expected in text
    assert "extraction/curation test" in text
    assert "not a knowledge-answering benchmark" in text


def test_trial_docs_preserve_the_reader_and_missing_answer_boundaries() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (README_PATH, GUIDE_PATH, EXPECTED_PATH)
    )

    for forbidden in (
        "TikuTong parses PDF",
        "TikuTong parses DOCX",
        "TikuTong performs OCR",
        "QBC parses PDF",
        "QBC parses DOCX",
        "QBC performs OCR",
        "TikuTong automatically fills missing answers",
        "题库通会自动补全答案",
    ):
        assert forbidden.casefold() not in combined.casefold()
    assert "Agent environment" in combined
    assert "没有答案就保持为空" in combined
    assert "不要根据知识或常识自行补答案" in combined


def test_own_bank_issue_template_has_required_frontmatter_and_sections() -> None:
    text = ISSUE_TEMPLATE_PATH.read_text(encoding="utf-8")

    assert text.startswith(
        "---\n"
        "name: Own-bank trial feedback\n"
        "about: Tell us how TikuTong worked with your own question bank\n"
        'title: "[Trial] "\n'
        "labels: usability\n"
        "---\n"
    )
    for heading in (
        "## Environment",
        "## Standard trial",
        "## My own question bank",
        "## Spot check",
        "## User experience",
        "## Privacy",
    ):
        assert heading in text
    assert "First point where you got stuck:" in text
    assert "Please do not upload private, copyrighted, or internal question-bank material." in text
