"""Standalone option-structure parsing for IP-05A; no Candidate or answer work."""

from __future__ import annotations

from dataclasses import dataclass, replace
import re

from qbcore.boundary_detector import BoundaryDecision
from qbcore.text_normalization import NormalizedDocument, SourceSpan


_MARKER = r"(?:\([A-Za-z]\)|（[A-Za-z]）|[A-Za-z][.、．)：)])"
_LEADING_MARKER_RE = re.compile(rf"^[ \t]*(?:[-*+][ \t]*)?(?P<marker>{_MARKER})")
_INLINE_MARKER_RE = re.compile(rf"(?<!\S)(?P<marker>{_MARKER})")
_LETTER_GROUP_RE = re.compile(r"^[ \t]*[A-Za-z]、[A-Za-z](?:两组|组)")


@dataclass(frozen=True)
class OptionMarkerEvidence:
    line_number: int
    raw_marker: str
    normalized_label: str
    marker_style: str
    start_position: int | None
    end_position: int | None
    confidence: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class OptionDecision:
    normalized_label: str
    raw_marker: str
    raw_text: str
    source_lines: tuple[int, ...]
    source_span: SourceSpan
    continuation_lines: tuple[int, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class OptionParseResult:
    options: tuple[OptionDecision, ...]
    detected: bool
    confidence: str
    warnings: tuple[str, ...]
    source_trace: tuple[SourceSpan, ...]
    marker_evidence: tuple[OptionMarkerEvidence, ...]


def _marker_parts(raw_marker: str) -> tuple[str, str]:
    label = raw_marker[1] if raw_marker.startswith(("(", "（")) else raw_marker[0]
    if raw_marker.startswith("("):
        style = "parenthesized"
    elif raw_marker.startswith("（"):
        style = "fullwidth_parenthesized"
    else:
        style = {
            ".": "dot",
            "、": "ideographic_comma",
            "．": "fullwidth_dot",
            ")": "close_parenthesis",
            "）": "fullwidth_close_parenthesis",
            "：": "fullwidth_colon",
        }[raw_marker[-1]]
    return label.upper(), style


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _span(source_id: str, lines: tuple[int, ...]) -> SourceSpan:
    return SourceSpan(source_id, lines[0], lines[-1])


def parse_option_structure(
    document: NormalizedDocument,
    boundaries: tuple[BoundaryDecision, ...],
) -> OptionParseResult:
    """Extract conservative option structure under supplied boundary context.

    A boundary starts a fresh option context. This function never creates
    questions, Candidates, answers, or source-file mutations.
    """

    if type(document) is not NormalizedDocument:
        raise TypeError("document must be a NormalizedDocument")
    if len(boundaries) != len(document.lines):
        raise ValueError("boundaries must have one decision per normalized line")
    if any(type(decision) is not BoundaryDecision for decision in boundaries):
        raise TypeError("boundaries must contain BoundaryDecision records")

    options: list[OptionDecision] = []
    evidence: list[OptionMarkerEvidence] = []
    warnings: list[str] = []
    active_question = False

    for line, boundary in zip(document.lines, boundaries, strict=True):
        if boundary.is_boundary:
            active_question = True
            continue
        if not active_question:
            continue

        text = line.normalized_text
        if _LETTER_GROUP_RE.match(text):
            _append_unique(warnings, "LETTER_GROUP_NOT_OPTION")
            continue
        leading = _LEADING_MARKER_RE.match(text)
        if leading is None:
            if options and text.strip():
                last = options[-1]
                lines = (*last.source_lines, line.original_line_number)
                options[-1] = replace(
                    last,
                    raw_text=f"{last.raw_text}\n{line.raw_text.strip()}",
                    source_lines=lines,
                    source_span=_span(document.source_id, lines),
                    continuation_lines=(*last.continuation_lines, line.original_line_number),
                )
            continue

        marker_start = leading.start("marker")
        marker_text = text[marker_start:]
        matches = list(_INLINE_MARKER_RE.finditer(marker_text))
        for index, match in enumerate(matches):
            raw_marker = match.group("marker")
            label, style = _marker_parts(raw_marker)
            next_start = matches[index + 1].start() if index + 1 < len(matches) else len(marker_text)
            option_text = marker_text[match.end() : next_start].strip()
            item_warnings: list[str] = []
            if raw_marker[0].islower():
                item_warnings.append("LOWERCASE_LABEL_NORMALIZED")
            if not option_text:
                item_warnings.append("INCOMPLETE_OPTION_MARKER")
                _append_unique(warnings, "INCOMPLETE_OPTION_MARKER")
            evidence.append(
                OptionMarkerEvidence(
                    line_number=line.normalized_line_number,
                    raw_marker=raw_marker,
                    normalized_label=label,
                    marker_style=style,
                    start_position=None,
                    end_position=None,
                    confidence="high" if option_text else "low",
                    warnings=tuple(item_warnings),
                )
            )
            if not option_text:
                continue
            line_number = line.original_line_number
            options.append(
                OptionDecision(
                    normalized_label=label,
                    raw_marker=raw_marker,
                    raw_text=option_text,
                    source_lines=(line_number,),
                    source_span=_span(document.source_id, (line_number,)),
                    continuation_lines=(),
                    warnings=tuple(item_warnings),
                )
            )

    seen: set[str] = set()
    expected = "A"
    for index, option in enumerate(options):
        item_warnings = list(option.warnings)
        if option.normalized_label in seen:
            _append_unique(item_warnings, "DUPLICATE_OPTION_LABEL")
            _append_unique(warnings, "DUPLICATE_OPTION_LABEL")
        elif option.normalized_label != expected:
            _append_unique(item_warnings, "OPTION_SEQUENCE_GAP")
            _append_unique(warnings, "OPTION_SEQUENCE_GAP")
        seen.add(option.normalized_label)
        if option.normalized_label >= expected:
            expected = chr(ord(option.normalized_label) + 1)
        options[index] = replace(option, warnings=tuple(item_warnings))

    confidence = "none" if not options else ("medium" if warnings else "high")
    return OptionParseResult(
        options=tuple(options),
        detected=bool(options),
        confidence=confidence,
        warnings=tuple(warnings),
        source_trace=tuple(option.source_span for option in options),
        marker_evidence=tuple(evidence),
    )


__all__ = [
    "OptionDecision",
    "OptionMarkerEvidence",
    "OptionParseResult",
    "parse_option_structure",
]
