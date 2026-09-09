from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest
import qbcore.single_choice_parser as parser_module

from qbcore.single_choice_parser import (
    ParseFinding,
    ParseResult,
    ParsedOption,
    ParsedSingleChoice,
    parse_single_choice,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "m2-parser"


def test_parser_records_have_narrow_frozen_fields_and_publishability() -> None:
    assert tuple(field.name for field in fields(ParsedOption)) == (
        "source_label",
        "text",
        "line",
    )
    assert tuple(field.name for field in fields(ParsedSingleChoice)) == (
        "display_number",
        "stem",
        "header_line",
        "options",
    )
    assert tuple(field.name for field in fields(ParseFinding)) == (
        "code",
        "line",
        "locator",
        "summary",
    )
    assert tuple(field.name for field in fields(ParseResult)) == (
        "questions",
        "findings",
        "question_like_block_count",
        "rejected_block_count",
    )

    option = ParsedOption(source_label="A", text="Alpha", line=2)
    question = ParsedSingleChoice(
        display_number="1",
        stem="Synthetic stem",
        header_line=1,
        options=(option, ParsedOption(source_label="B", text="Beta", line=3)),
    )
    result = ParseResult(
        questions=(question,),
        findings=(),
        question_like_block_count=1,
        rejected_block_count=0,
    )

    assert result.publishable is True
    assert ParseResult((), (), 0, 0).publishable is False
    assert ParseResult(
        (question,),
        (ParseFinding("QB-STRUCTURE-AMBIGUOUS", 1, "line:1", "Synthetic finding."),),
        1,
        0,
    ).publishable is False
    with pytest.raises(FrozenInstanceError):
        option.text = "Changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.questions = ()  # type: ignore[misc]


def test_supported_grammar_preserves_internal_text_and_uses_logical_line_numbers() -> None:
    text = (
        "Ordinary prose is ignored.\r\n"
        "\t1) [single_choice] \tStem  keeps\tinternal characters \t\r"
        "\r\n"
        "   - A. \tAlpha  keeps\tspacing  \t\n"
        "\t* B) Beta\r"
        "+ C. Gamma"
    )

    result = parse_single_choice(text)

    assert result == ParseResult(
        questions=(
            ParsedSingleChoice(
                display_number="1",
                stem="Stem  keeps\tinternal characters",
                header_line=2,
                options=(
                    ParsedOption("A", "Alpha  keeps\tspacing", 4),
                    ParsedOption("B", "Beta", 5),
                    ParsedOption("C", "Gamma", 6),
                ),
            ),
        ),
        findings=(),
        question_like_block_count=1,
        rejected_block_count=0,
    )
    assert result.publishable is True


@pytest.mark.parametrize(
    "separator",
    ("\u2028", "\u2029", "\u0085", "\v", "\f", "\x1c", "\x1d", "\x1e"),
    ids=(
        "line-separator",
        "paragraph-separator",
        "next-line",
        "vertical-tab",
        "form-feed",
        "file-separator",
        "group-separator",
        "record-separator",
    ),
)
def test_only_lf_crlf_and_cr_create_logical_lines(separator: str) -> None:
    accidental_block = parse_single_choice(
        f"1. [single_choice] Synthetic stem{separator}"
        f"- A. Alpha{separator}"
        "- B. Beta"
    )
    locator_probe = parse_single_choice(
        f"Ordinary{separator}prose stays on one logical line\n"
        "2. [single_choice] Synthetic stem\n"
        "- A. Alpha\n"
        "- B. Beta"
    )

    assert accidental_block.questions == ()
    assert accidental_block.question_like_block_count == 1
    assert accidental_block.rejected_block_count == 1
    assert accidental_block.findings[0].locator == "line:1"
    assert len(locator_probe.questions) == 1
    assert locator_probe.questions[0].header_line == 2
    assert [option.line for option in locator_probe.questions[0].options] == [3, 4]


def test_strict_two_fixture_accepts_header_option_and_bullet_variants_at_eof() -> None:
    text = (FIXTURE_ROOT / "strict-two.txt").read_text(encoding="utf-8")

    result = parse_single_choice(text)

    assert [question.display_number for question in result.questions] == ["1", "17"]
    assert [question.header_line for question in result.questions] == [1, 5]
    assert [[option.source_label for option in question.options] for question in result.questions] == [
        ["A", "B"],
        ["A", "B"],
    ]
    assert [[option.line for option in question.options] for question in result.questions] == [
        [2, 3],
        [6, 7],
    ]
    assert [[option.text for option in question.options] for question in result.questions] == [
        ["Alpha", "Beta"],
        ["First", "Second"],
    ]
    assert result.findings == ()
    assert result.question_like_block_count == 2
    assert result.rejected_block_count == 0


def test_strict_seven_fixture_yields_exact_questions_and_option_counts() -> None:
    text = (FIXTURE_ROOT / "strict-seven.md").read_text(encoding="utf-8")

    first = parse_single_choice(text)
    second = parse_single_choice(text)

    assert first == second
    assert len(first.questions) == 7
    assert [len(question.options) for question in first.questions] == [4, 4, 4, 4, 4, 3, 3]
    assert first.question_like_block_count == 7
    assert first.rejected_block_count == 0
    assert first.findings == ()


def test_exactly_twenty_six_contiguous_options_are_accepted() -> None:
    option_lines = tuple(
        f"- {chr(ord('A') + index)}. Option {index + 1}"
        for index in range(26)
    )

    result = parse_single_choice(
        "\n".join(("26. [single_choice] Boundary question", *option_lines))
    )

    assert len(result.questions) == 1
    assert [option.source_label for option in result.questions[0].options] == list(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    )
    assert result.findings == ()
    assert result.question_like_block_count == 1
    assert result.rejected_block_count == 0
    assert result.publishable is True


@pytest.mark.parametrize(
    "options",
    [
        ("- A. Only",),
        tuple(f"- {chr(65 + index)}. Option {index + 1}" for index in range(26))
        + ("- A. Option 27",),
        ("- B. First", "- C. Second"),
        ("- A. First", "- C. Third"),
        ("- A. First", "- B. Second", "- B. Repeated"),
        ("- A. First", "- b. Lowercase", "- C. Third"),
    ],
    ids=("one-option", "twenty-seven-options", "first-not-a", "gap", "repeat", "lowercase"),
)
def test_invalid_option_cardinality_or_labels_rejects_the_whole_block(
    options: tuple[str, ...],
) -> None:
    text = "\n".join(("9. [single_choice] Synthetic stem", *options))

    result = parse_single_choice(text)

    assert result.questions == ()
    assert result.question_like_block_count == 1
    assert result.rejected_block_count == 1
    assert result.findings == (
        ParseFinding(
            code="QB-STRUCTURE-AMBIGUOUS",
            line=1,
            locator="line:1",
            summary="Question block does not satisfy supported option structure.",
        ),
    )
    assert result.publishable is False


def test_question_like_bracket_marker_closes_a_block_with_stable_finding_order() -> None:
    text = "\n".join(
        (
            "1. [single_choice] Accepted first",
            "- A. Alpha",
            "- B. Beta",
            "2) [Single_Choice] Unsupported exact marker",
            "- A. Ignored outside supported block",
            "- B. Ignored outside supported block",
            "3. [single_choice] Rejected last",
            "- A. Only",
        )
    )

    first = parse_single_choice(text)
    second = parse_single_choice(text)

    assert first == second
    assert [question.display_number for question in first.questions] == ["1"]
    assert first.question_like_block_count == 3
    assert first.rejected_block_count == 2
    assert first.findings == tuple(
        sorted(first.findings, key=lambda finding: (finding.line, finding.code, finding.summary))
    )
    assert first.findings == (
        ParseFinding(
            code="QB-TYPE-UNSUPPORTED",
            line=4,
            locator="line:4",
            summary="Question-like header uses an unsupported type marker.",
        ),
        ParseFinding(
            code="QB-STRUCTURE-AMBIGUOUS",
            line=7,
            locator="line:7",
            summary="Question block does not satisfy supported option structure.",
        ),
    )


def test_header_marker_is_case_sensitive_and_leading_non_ascii_space_is_not_accepted() -> None:
    case_mismatch = parse_single_choice(
        "1. [SINGLE_CHOICE] Synthetic stem\n- A. Alpha\n- B. Beta"
    )
    non_ascii_indent = parse_single_choice(
        "\u00a01. [single_choice] Synthetic stem\n- A. Alpha\n- B. Beta"
    )

    assert case_mismatch.questions == ()
    assert case_mismatch.question_like_block_count == 1
    assert case_mismatch.rejected_block_count == 1
    assert case_mismatch.findings == (
        ParseFinding(
            code="QB-TYPE-UNSUPPORTED",
            line=1,
            locator="line:1",
            summary="Question-like header uses an unsupported type marker.",
        ),
    )
    assert non_ascii_indent == ParseResult(
        questions=(),
        findings=(
            ParseFinding(
                code="QB-STRUCTURE-AMBIGUOUS",
                line=2,
                locator="line:2",
                summary="Option-like line appears outside a question block.",
            ),
            ParseFinding(
                code="QB-STRUCTURE-AMBIGUOUS",
                line=3,
                locator="line:3",
                summary="Option-like line appears outside a question block.",
            ),
        ),
        question_like_block_count=0,
        rejected_block_count=0,
    )


@pytest.mark.parametrize(
    ("body", "expected_line", "expected_summary"),
    [
        (
            "1. [single_choice]   \n- A. Alpha\n- B. Beta",
            1,
            "Question-like header does not match the supported grammar.",
        ),
        (
            "1. [single_choice] Synthetic stem\n- A.   \n- B. Beta",
            2,
            "Question block contains a malformed option line.",
        ),
        (
            "1. [single_choice] Synthetic stem\nUnknown synthetic line.\n- A. Alpha\n- B. Beta",
            2,
            "Question block contains an unsupported nonblank line.",
        ),
    ],
    ids=("empty-stem", "empty-option", "unknown-in-block-line"),
)
def test_malformed_block_finding_is_rooted_at_first_offending_line(
    body: str,
    expected_line: int,
    expected_summary: str,
) -> None:
    result = parse_single_choice(body)

    assert result.questions == ()
    assert result.question_like_block_count == 1
    assert result.rejected_block_count == 1
    assert result.findings == (
        ParseFinding(
            code="QB-STRUCTURE-AMBIGUOUS",
            line=expected_line,
            locator=f"line:{expected_line}",
            summary=expected_summary,
        ),
    )
    assert result.publishable is False


def test_new_header_closes_rejected_block_and_keeps_later_question_diagnostic() -> None:
    result = parse_single_choice(
        "1. [single_choice] Rejected synthetic stem\n"
        "Unknown synthetic line.\n"
        "- A. Alpha\n"
        "- B. Beta\n"
        "2. [single_choice] Accepted synthetic stem\n"
        "- A. First\n"
        "- B. Second"
    )

    assert [question.display_number for question in result.questions] == ["2"]
    assert result.question_like_block_count == 2
    assert result.rejected_block_count == 1
    assert result.findings == (
        ParseFinding(
            code="QB-STRUCTURE-AMBIGUOUS",
            line=2,
            locator="line:2",
            summary="Question block contains an unsupported nonblank line.",
        ),
    )
    assert result.publishable is False


def test_malformed_fixture_has_exact_sanitized_finding() -> None:
    result = parse_single_choice(
        (FIXTURE_ROOT / "malformed.md").read_text(encoding="utf-8")
    )

    assert result == ParseResult(
        questions=(),
        findings=(
            ParseFinding(
                code="QB-STRUCTURE-AMBIGUOUS",
                line=1,
                locator="line:1",
                summary="Question block does not satisfy supported option structure.",
            ),
        ),
        question_like_block_count=1,
        rejected_block_count=1,
    )


@pytest.mark.parametrize(
    "marker",
    ("multiple_choice", "true_false", "synthetic_other", "Single_Choice", ""),
)
def test_any_question_like_bracket_marker_other_than_exact_supported_is_type_unsupported(
    marker: str,
) -> None:
    result = parse_single_choice(
        f"7. [{marker}] Synthetic stem\n- A. Alpha\n- B. Beta"
    )

    assert result == ParseResult(
        questions=(),
        findings=(
            ParseFinding(
                code="QB-TYPE-UNSUPPORTED",
                line=1,
                locator="line:1",
                summary="Question-like header uses an unsupported type marker.",
            ),
        ),
        question_like_block_count=1,
        rejected_block_count=1,
    )


def test_unsupported_fixture_and_valid_block_return_diagnostics_without_publication() -> None:
    unsupported = (FIXTURE_ROOT / "unsupported-type.md").read_text(encoding="utf-8")
    result = parse_single_choice(
        unsupported
        + "\n2. [single_choice] Accepted synthetic stem\n"
        + "- A. Alpha\n- B. Beta"
    )

    assert [question.display_number for question in result.questions] == ["2"]
    assert result.findings == (
        ParseFinding(
            code="QB-TYPE-UNSUPPORTED",
            line=1,
            locator="line:1",
            summary="Question-like header uses an unsupported type marker.",
        ),
    )
    assert result.question_like_block_count == 2
    assert result.rejected_block_count == 1
    assert result.publishable is False


def test_missing_marker_header_and_outside_option_have_distinct_structure_findings() -> None:
    result = parse_single_choice(
        "- A. Synthetic loose option\n"
        "5. Synthetic question without marker\n"
        "- A. Ignored inside rejected question-like block\n"
        "- B. Ignored inside rejected question-like block"
    )

    assert result.questions == ()
    assert result.question_like_block_count == 1
    assert result.rejected_block_count == 1
    assert result.findings == (
        ParseFinding(
            code="QB-STRUCTURE-AMBIGUOUS",
            line=1,
            locator="line:1",
            summary="Option-like line appears outside a question block.",
        ),
        ParseFinding(
            code="QB-STRUCTURE-AMBIGUOUS",
            line=2,
            locator="line:2",
            summary="Question-like header does not match the supported grammar.",
        ),
    )


def test_headings_prose_blanks_and_answer_like_text_outside_blocks_are_ignored() -> None:
    result = parse_single_choice(
        "# Synthetic heading\n\n"
        "Ordinary synthetic prose.\n"
        "Answer: B\n"
        "Correct option is B."
    )

    assert result == ParseResult((), (), 0, 0)


def test_answer_like_text_inside_block_is_ordinary_unknown_text_and_rejects_block() -> None:
    result = parse_single_choice(
        "1. [single_choice] Synthetic stem\n"
        "- A. Alpha\n"
        "Answer: A\n"
        "- B. Beta"
    )

    assert result.findings == (
        ParseFinding(
            code="QB-STRUCTURE-AMBIGUOUS",
            line=3,
            locator="line:3",
            summary="Question block contains an unsupported nonblank line.",
        ),
    )
    assert result.questions == ()
    assert result.rejected_block_count == 1


def test_fenced_fixture_ignores_question_content_inside_backticks() -> None:
    result = parse_single_choice(
        (FIXTURE_ROOT / "fenced.md").read_text(encoding="utf-8")
    )

    assert [question.display_number for question in result.questions] == ["1"]
    assert result.questions[0].header_line == 7
    assert result.question_like_block_count == 1
    assert result.rejected_block_count == 0
    assert result.findings == ()
    assert result.publishable is True


@pytest.mark.parametrize(
    ("opener", "ignored_closers", "closer"),
    [
        ("```python", ("~~~", "``"), "````"),
        ("~~~~ synthetic", ("```", "~~~"), "~~~~~"),
    ],
    ids=("backtick-longer-close", "tilde-opposite-and-shorter-do-not-close"),
)
def test_fence_remembers_character_and_minimum_opening_length(
    opener: str,
    ignored_closers: tuple[str, ...],
    closer: str,
) -> None:
    text = "\n".join(
        (
            opener,
            "1. [single_choice] Fenced synthetic stem",
            "- A. Ignored first",
            *ignored_closers,
            "- B. Ignored second",
            closer,
            "2. [single_choice] Visible synthetic stem",
            "- A. Alpha",
            "- B. Beta",
        )
    )

    result = parse_single_choice(text)

    assert [question.display_number for question in result.questions] == ["2"]
    assert result.question_like_block_count == 1
    assert result.rejected_block_count == 0
    assert result.findings == ()


def test_closing_fence_requires_only_surrounding_whitespace() -> None:
    result = parse_single_choice(
        "```\n"
        "``` trailing synthetic text\n"
        "1. [single_choice] Still fenced\n"
        "- A. Ignored\n"
        "- B. Ignored\n"
        "  ```  \n"
        "2. [single_choice] Visible synthetic stem\n"
        "- A. Alpha\n"
        "- B. Beta"
    )

    assert [question.display_number for question in result.questions] == ["2"]
    assert result.question_like_block_count == 1
    assert result.findings == ()


def test_unclosed_fence_reports_opening_locator_without_counting_fenced_blocks() -> None:
    result = parse_single_choice(
        "Synthetic prose\n"
        "~~~text\n"
        "1. [single_choice] Ignored synthetic stem\n"
        "- A. Ignored\n"
        "- B. Ignored"
    )

    assert result == ParseResult(
        questions=(),
        findings=(
            ParseFinding(
                code="QB-STRUCTURE-AMBIGUOUS",
                line=2,
                locator="line:2",
                summary="Markdown fence is not closed.",
            ),
        ),
        question_like_block_count=0,
        rejected_block_count=0,
    )


def test_fence_opened_inside_question_rejects_block_then_ignores_fenced_content() -> None:
    result = parse_single_choice(
        "1. [single_choice] Rejected synthetic stem\n"
        "- A. Alpha\n"
        "```text\n"
        "2. [single_choice] Ignored fenced stem\n"
        "- A. Ignored\n"
        "- B. Ignored\n"
        "```\n"
        "3. [single_choice] Accepted synthetic stem\n"
        "- A. First\n"
        "- B. Second"
    )

    assert [question.display_number for question in result.questions] == ["3"]
    assert result.question_like_block_count == 2
    assert result.rejected_block_count == 1
    assert result.findings == (
        ParseFinding(
            code="QB-STRUCTURE-AMBIGUOUS",
            line=3,
            locator="line:3",
            summary="Question block contains an unsupported nonblank line.",
        ),
    )
    assert result.publishable is False


@pytest.mark.parametrize(
    ("tail", "expected_display_numbers", "expected_block_count"),
    [
        ("", [], 1),
        (
            "\n2. [single_choice] Accepted synthetic stem\n"
            "- A. First\n"
            "- B. Second",
            ["2"],
            2,
        ),
    ],
    ids=("eof", "next-header"),
)
def test_fence_opener_preserves_an_earlier_block_finding(
    tail: str,
    expected_display_numbers: list[str],
    expected_block_count: int,
) -> None:
    result = parse_single_choice(
        "1. [single_choice] Rejected synthetic stem\n"
        "Unknown synthetic line.\n"
        "```text\n"
        "9. [single_choice] Ignored fenced stem\n"
        "- A. Ignored\n"
        "- B. Ignored\n"
        "```"
        + tail
    )

    assert [question.display_number for question in result.questions] == (
        expected_display_numbers
    )
    assert result.question_like_block_count == expected_block_count
    assert result.rejected_block_count == 1
    assert result.findings == (
        ParseFinding(
            code="QB-STRUCTURE-AMBIGUOUS",
            line=2,
            locator="line:2",
            summary="Question block contains an unsupported nonblank line.",
        ),
    )


def test_fence_suspends_active_block_without_turning_later_option_into_outside_finding() -> None:
    result = parse_single_choice(
        "1. [single_choice] Rejected synthetic stem\n"
        "- A. Alpha\n"
        "```text\n"
        "9. [multiple_choice] Ignored fenced content\n"
        "```\n"
        "- B. Beta"
    )

    assert result == ParseResult(
        questions=(),
        findings=(
            ParseFinding(
                code="QB-STRUCTURE-AMBIGUOUS",
                line=3,
                locator="line:3",
                summary="Question block contains an unsupported nonblank line.",
            ),
        ),
        question_like_block_count=1,
        rejected_block_count=1,
    )


@pytest.mark.parametrize(
    "option_lines",
    [
        ("- a. Lowercase", "- B. Beta"),
        ("- B. First is not A", "- C. Third"),
        ("- A. Alpha", "- C. Gap"),
        ("- A. Alpha", "- B. Beta", "- B. Repeated"),
        tuple(
            f"- {chr(ord('A') + index)}. Option {index + 1}"
            for index in range(26)
        )
        + ("- A. Twenty seventh",),
    ],
    ids=("lowercase", "first-not-a", "gap", "duplicate", "twenty-seventh"),
)
def test_known_option_violation_latches_before_later_unknown_text(
    option_lines: tuple[str, ...],
) -> None:
    result = parse_single_choice(
        "\n".join(
            (
                "1. [single_choice] Rejected synthetic stem",
                *option_lines,
                "Later unknown synthetic text.",
            )
        )
    )

    assert result == ParseResult(
        questions=(),
        findings=(
            ParseFinding(
                code="QB-STRUCTURE-AMBIGUOUS",
                line=1,
                locator="line:1",
                summary="Question block does not satisfy supported option structure.",
            ),
        ),
        question_like_block_count=1,
        rejected_block_count=1,
    )


@pytest.mark.parametrize(
    ("near_miss", "expected_code", "expected_summary"),
    [
        (
            "0. [single_choice] Zero is outside positive grammar",
            "QB-STRUCTURE-AMBIGUOUS",
            "Question-like header does not match the supported grammar.",
        ),
        (
            "01) [single_choice] Leading zero is outside positive grammar",
            "QB-STRUCTURE-AMBIGUOUS",
            "Question-like header does not match the supported grammar.",
        ),
        (
            "1.[single_choice] Missing required space",
            "QB-STRUCTURE-AMBIGUOUS",
            "Question-like header does not match the supported grammar.",
        ),
        (
            "1.[multiple_choice] Missing required space",
            "QB-TYPE-UNSUPPORTED",
            "Question-like header uses an unsupported type marker.",
        ),
        (
            "00.[true_false] Invalid number and unsupported marker",
            "QB-TYPE-UNSUPPORTED",
            "Question-like header uses an unsupported type marker.",
        ),
    ],
    ids=(
        "zero",
        "leading-zero",
        "missing-space-supported",
        "missing-space-unsupported",
        "zero-and-unsupported",
    ),
)
def test_numbered_near_miss_is_diagnostic_and_blocks_mixed_file_publication(
    near_miss: str,
    expected_code: str,
    expected_summary: str,
) -> None:
    result = parse_single_choice(
        near_miss
        + "\n- A. Ignored rejected option\n"
        + "- B. Ignored rejected option\n"
        + "2. [single_choice] Accepted synthetic stem\n"
        + "- A. Alpha\n"
        + "- B. Beta"
    )

    assert [question.display_number for question in result.questions] == ["2"]
    assert result.findings == (
        ParseFinding(
            code=expected_code,
            line=1,
            locator="line:1",
            summary=expected_summary,
        ),
    )
    assert result.question_like_block_count == 2
    assert result.rejected_block_count == 1
    assert result.publishable is False


def test_close_resets_all_block_state_across_rejected_near_miss_transition() -> None:
    result = parse_single_choice(
        "1. [single_choice] Accepted first stem\n"
        "- A. First alpha\n"
        "- B. First beta\n"
        "01. [single_choice] Rejected numbered near miss\n"
        "- A. Ignored rejected alpha\n"
        "- B. Ignored rejected beta\n"
        "2. [single_choice] Accepted second stem\n"
        "- A. Second alpha\n"
        "- B. Second beta"
    )

    assert [question.display_number for question in result.questions] == ["1", "2"]
    assert [[option.text for option in question.options] for question in result.questions] == [
        ["First alpha", "First beta"],
        ["Second alpha", "Second beta"],
    ]
    assert result.findings == (
        ParseFinding(
            code="QB-STRUCTURE-AMBIGUOUS",
            line=4,
            locator="line:4",
            summary="Question-like header does not match the supported grammar.",
        ),
    )
    assert result.question_like_block_count == 3
    assert result.rejected_block_count == 1


def test_decimal_version_and_unspaced_general_prose_are_not_question_like() -> None:
    result = parse_single_choice(
        "2026.08 release note\n"
        "3.14 synthetic value\n"
        "1.General prose without delimiter whitespace\n"
        "\n"
        "2. [single_choice] Accepted synthetic stem\n"
        "- A. Alpha\n"
        "- B. Beta"
    )

    assert [question.display_number for question in result.questions] == ["2"]
    assert result.questions[0].header_line == 5
    assert result.findings == ()
    assert result.question_like_block_count == 1
    assert result.rejected_block_count == 0
    assert result.publishable is True


def test_irreversibly_invalid_block_stops_allocating_options_under_stress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allocation_count = 0

    def count_option_allocation(
        source_label: str,
        text: str,
        line: int,
    ) -> ParsedOption:
        nonlocal allocation_count
        allocation_count += 1
        return ParsedOption(source_label, text, line)

    monkeypatch.setattr(parser_module, "ParsedOption", count_option_allocation)
    valid_options = tuple(
        f"- {chr(ord('A') + index)}. Valid option {index + 1}"
        for index in range(26)
    )
    excess_options = tuple(
        f"- A. Ignored excess option {index + 1}"
        for index in range(150)
    )

    result = parse_single_choice(
        "\n".join(
            (
                "1. [single_choice] Rejected synthetic stem",
                *valid_options,
                *excess_options,
            )
        )
    )

    assert allocation_count == 26
    assert result == ParseResult(
        questions=(),
        findings=(
            ParseFinding(
                code="QB-STRUCTURE-AMBIGUOUS",
                line=1,
                locator="line:1",
                summary="Question block does not satisfy supported option structure.",
            ),
        ),
        question_like_block_count=1,
        rejected_block_count=1,
    )
