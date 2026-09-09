"""Pure parser for the Milestone 2 supported single-choice grammar."""

from __future__ import annotations

from dataclasses import dataclass
import re


_HEADER_RE = re.compile(
    r"^[ \t]*(?P<number>[1-9][0-9]*)[.)][ \t]+"
    r"\[single_choice\][ \t]+(?P<stem>\S(?:.*\S)?)[ \t]*$"
)
_OPTION_RE = re.compile(
    r"^[ \t]*[-*+][ \t]+(?P<label>[A-Z])[.)][ \t]+"
    r"(?P<text>\S(?:.*\S)?)[ \t]*$"
)
_LOWERCASE_OPTION_RE = re.compile(
    r"^[ \t]*[-*+][ \t]+[a-z][.)][ \t]+\S(?:.*\S)?[ \t]*$"
)
_OPTION_LIKE_RE = re.compile(r"^[ \t]*[-*+][ \t]+[A-Za-z][.)].*$")
_DIAGNOSTIC_HEADER_RE = re.compile(
    r"^[ \t]*[0-9]+[.)](?=[ \t]|\[|$)[ \t]*(?P<body>.*)$"
)
_BRACKET_MARKER_RE = re.compile(r"^\[[^\]\r\n]*\]")
_FENCE_OPEN_RE = re.compile(r"^[ \t]*(?P<fence>`{3,}|~{3,}).*$")

_STRUCTURE_CODE = "QB-STRUCTURE-AMBIGUOUS"
_UNSUPPORTED_TYPE_CODE = "QB-TYPE-UNSUPPORTED"
_INVALID_OPTIONS_SUMMARY = "Question block does not satisfy supported option structure."
_UNSUPPORTED_HEADER_SUMMARY = "Question-like header does not match the supported grammar."
_UNSUPPORTED_TYPE_SUMMARY = "Question-like header uses an unsupported type marker."
_OUTSIDE_OPTION_SUMMARY = "Option-like line appears outside a question block."
_MALFORMED_OPTION_SUMMARY = "Question block contains a malformed option line."
_UNKNOWN_BLOCK_LINE_SUMMARY = "Question block contains an unsupported nonblank line."
_UNCLOSED_FENCE_SUMMARY = "Markdown fence is not closed."


@dataclass(frozen=True)
class ParsedOption:
    source_label: str
    text: str
    line: int


@dataclass(frozen=True)
class ParsedSingleChoice:
    display_number: str
    stem: str
    header_line: int
    options: tuple[ParsedOption, ...]


@dataclass(frozen=True)
class ParseFinding:
    code: str
    line: int
    locator: str
    summary: str


@dataclass(frozen=True)
class ParseResult:
    questions: tuple[ParsedSingleChoice, ...]
    findings: tuple[ParseFinding, ...]
    question_like_block_count: int
    rejected_block_count: int

    @property
    def publishable(self) -> bool:
        return bool(self.questions) and not self.findings


def _finding(code: str, line: int, summary: str) -> ParseFinding:
    return ParseFinding(
        code=code,
        line=line,
        locator=f"line:{line}",
        summary=summary,
    )


def _structure_finding(line: int, summary: str) -> ParseFinding:
    return _finding(_STRUCTURE_CODE, line, summary)


def _is_fence_close(line: str, fence_character: str, minimum_length: int) -> bool:
    stripped = line.strip(" \t")
    return (
        len(stripped) >= minimum_length
        and stripped == fence_character * len(stripped)
    )


def _finalize_supported_block(
    display_number: str,
    stem: str,
    header_line: int,
    options: list[ParsedOption],
    has_lowercase_option: bool,
) -> tuple[ParsedSingleChoice | None, ParseFinding | None]:
    labels = [option.source_label for option in options]
    expected_labels = [chr(ord("A") + index) for index in range(len(options))]
    if has_lowercase_option or not 2 <= len(options) <= 26 or labels != expected_labels:
        return None, _structure_finding(header_line, _INVALID_OPTIONS_SUMMARY)
    return (
        ParsedSingleChoice(
            display_number=display_number,
            stem=stem,
            header_line=header_line,
            options=tuple(options),
        ),
        None,
    )


def parse_single_choice(text: str) -> ParseResult:
    """Parse an already decoded string without performing external I/O."""

    questions: list[ParsedSingleChoice] = []
    findings: list[ParseFinding] = []
    question_like_block_count = 0
    rejected_block_count = 0

    display_number: str | None = None
    stem = ""
    header_line = 0
    options: list[ParsedOption] = []
    has_lowercase_option = False
    block_finding: ParseFinding | None = None
    discarding_rejected_block = False
    fence_character: str | None = None
    fence_length = 0
    fence_open_line = 0

    def close_supported_block() -> None:
        nonlocal display_number, stem, header_line, options
        nonlocal has_lowercase_option, block_finding, rejected_block_count
        if display_number is None:
            return
        if block_finding is not None:
            rejected_block_count += 1
            findings.append(block_finding)
        else:
            question, finding = _finalize_supported_block(
                display_number,
                stem,
                header_line,
                options,
                has_lowercase_option,
            )
            if question is not None:
                questions.append(question)
            else:
                rejected_block_count += 1
                assert finding is not None
                findings.append(finding)
        display_number = None
        stem = ""
        header_line = 0
        options = []
        has_lowercase_option = False
        block_finding = None

    logical_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for line_number, line in enumerate(logical_lines, start=1):
        if fence_character is not None:
            if _is_fence_close(line, fence_character, fence_length):
                fence_character = None
                fence_length = 0
                fence_open_line = 0
            continue

        fence_match = _FENCE_OPEN_RE.fullmatch(line)
        if fence_match is not None:
            if display_number is not None:
                if block_finding is None:
                    block_finding = _structure_finding(
                        line_number,
                        _UNKNOWN_BLOCK_LINE_SUMMARY,
                    )
            fence = fence_match.group("fence")
            fence_character = fence[0]
            fence_length = len(fence)
            fence_open_line = line_number
            continue

        header_match = _HEADER_RE.fullmatch(line)
        if header_match is not None:
            close_supported_block()
            question_like_block_count += 1
            discarding_rejected_block = False
            display_number = header_match.group("number")
            stem = header_match.group("stem")
            header_line = line_number
            options = []
            has_lowercase_option = False
            block_finding = None
            continue

        question_like_match = _DIAGNOSTIC_HEADER_RE.fullmatch(line)
        if question_like_match is not None:
            close_supported_block()
            question_like_block_count += 1
            rejected_block_count += 1
            body = question_like_match.group("body")
            if (
                _BRACKET_MARKER_RE.match(body) is not None
                and not body.startswith("[single_choice]")
            ):
                findings.append(
                    _finding(
                        _UNSUPPORTED_TYPE_CODE,
                        line_number,
                        _UNSUPPORTED_TYPE_SUMMARY,
                    )
                )
            else:
                findings.append(
                    _structure_finding(line_number, _UNSUPPORTED_HEADER_SUMMARY)
                )
            discarding_rejected_block = True
            continue

        if display_number is None:
            if (
                not discarding_rejected_block
                and _OPTION_LIKE_RE.fullmatch(line) is not None
            ):
                findings.append(
                    _structure_finding(line_number, _OUTSIDE_OPTION_SUMMARY)
                )
            continue

        option_match = _OPTION_RE.fullmatch(line)
        if option_match is not None:
            if block_finding is not None:
                continue
            if len(options) >= 26:
                block_finding = _structure_finding(
                    header_line,
                    _INVALID_OPTIONS_SUMMARY,
                )
                continue
            label = option_match.group("label")
            expected_label = chr(ord("A") + len(options))
            if label != expected_label:
                block_finding = _structure_finding(
                    header_line,
                    _INVALID_OPTIONS_SUMMARY,
                )
                continue
            options.append(
                ParsedOption(
                    source_label=label,
                    text=option_match.group("text"),
                    line=line_number,
                )
            )
        elif _LOWERCASE_OPTION_RE.fullmatch(line) is not None:
            has_lowercase_option = True
            if block_finding is None:
                block_finding = _structure_finding(
                    header_line,
                    _INVALID_OPTIONS_SUMMARY,
                )
        elif _OPTION_LIKE_RE.fullmatch(line) is not None:
            if block_finding is None:
                block_finding = _structure_finding(
                    line_number,
                    _MALFORMED_OPTION_SUMMARY,
                )
        elif line.strip(" \t") and block_finding is None:
            block_finding = _structure_finding(
                line_number,
                _UNKNOWN_BLOCK_LINE_SUMMARY,
            )

    close_supported_block()
    if fence_character is not None:
        findings.append(
            _structure_finding(fence_open_line, _UNCLOSED_FENCE_SUMMARY)
        )
    findings.sort(key=lambda finding: (finding.line, finding.code, finding.summary))
    return ParseResult(
        questions=tuple(questions),
        findings=tuple(findings),
        question_like_block_count=question_like_block_count,
        rejected_block_count=rejected_block_count,
    )
