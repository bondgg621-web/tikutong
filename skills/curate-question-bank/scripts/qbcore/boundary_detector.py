"""Standalone, multi-signal structural question-boundary detector for IP-04."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

from qbcore.text_normalization import NormalizedDocument, SourceSpan


BoundaryStrength = Literal["STRONG", "MEDIUM", "WEAK", "NONE"]

_NUMBER_MARKER_RE = re.compile(
    r"^[ \t]*(?:(?P<parenthesized>\((?P<paren_number>[1-9][0-9]*)\)|"
    r"（(?P<fullwidth_number>[1-9][0-9]*)）)|"
    r"(?P<number>[1-9][0-9]*)(?P<marker>[.)、．]))[ \t]*(?P<stem>.*)$"
)
_CHINESE_MARKER_RE = re.compile(r"^[ \t]*(?P<marker>[一二三四五六七八九十])、[ \t]*(?P<stem>.*)$")
_OPTION_RE = re.compile(
    r"^[ \t]*[-*+]?[ \t]*(?P<label>[A-Z])[.)、．][ \t]+\S(?:.*\S)?[ \t]*$"
)
_DATE_RE = re.compile(r"^[0-9]{4}[.．][0-9]{1,2}[.．][0-9]{1,2}(?:\D|$)")
_DECIMAL_MEASUREMENT_RE = re.compile(
    r"^[0-9]+[.．][0-9]+(?:[ \t]*(?:mg|g/L|mmHg|℃|cm|mm|ml))?(?:\D|$)",
    re.IGNORECASE,
)
_MEASUREMENT_TEXT_RE = re.compile(
    r"^(?:患者?体温\s*[0-9]+[.．]?[0-9]*℃|(?:Hb|PaO2)\s*[0-9]+(?:[ \t]*(?:g/L|mmHg))?)$",
    re.IGNORECASE,
)
_INTERCOSTAL_RE = re.compile(r"^第[0-9]+[、,][0-9]+肋间")
_PAGE_RE = re.compile(r"^(?:第\s*)?[0-9]+\s*页$|^页\s*[0-9]+$")


@dataclass(frozen=True)
class BoundaryEvidence:
    signal_name: str
    passed: bool
    score: int
    detail: str


@dataclass(frozen=True)
class BoundaryDecision:
    line_number: int
    decision: BoundaryStrength
    is_boundary: bool
    question_number: int | None
    question_marker: str | None
    stem_preview: str | None
    evidence: tuple[BoundaryEvidence, ...]
    warnings: tuple[str, ...]
    source_span: SourceSpan


def _section_heading(text: str) -> bool:
    compact = text.strip()
    return bool(
        re.match(r"^第[一二三四五六七八九十0-9]+[章节]", compact)
        or compact in {"单项选择题", "多项选择题", "课程名称"}
    )


def _numeric_false_positive(text: str) -> bool:
    compact = text.strip()
    return bool(
        _DATE_RE.match(compact)
        or _DECIMAL_MEASUREMENT_RE.match(compact)
        or _MEASUREMENT_TEXT_RE.fullmatch(compact)
        or _INTERCOSTAL_RE.match(compact)
        or _PAGE_RE.fullmatch(compact)
    )


def _marker_parts(text: str) -> tuple[int | None, str | None, str] | None:
    numbered = _NUMBER_MARKER_RE.fullmatch(text)
    if numbered is not None:
        number_text = (
            numbered.group("paren_number")
            or numbered.group("fullwidth_number")
            or numbered.group("number")
        )
        marker = numbered.group("parenthesized") or numbered.group("marker")
        return int(number_text), marker, numbered.group("stem").strip()
    chinese = _CHINESE_MARKER_RE.fullmatch(text)
    if chinese is not None:
        return None, chinese.group("marker") + "、", chinese.group("stem").strip()
    return None


def _stem_after_type_marker(stem: str) -> tuple[str, bool]:
    if stem.startswith("[single_choice]"):
        return stem[len("[single_choice]") :].strip(), True
    return stem, False


def _plausible_stem(stem: str) -> bool:
    if len(stem) < 4:
        return False
    if _numeric_false_positive(stem):
        return False
    return any(not character.isdigit() for character in stem)


def detect_boundaries(document: NormalizedDocument) -> tuple[BoundaryDecision, ...]:
    """Classify every normalized line without changing parser or source state."""

    if type(document) is not NormalizedDocument:
        raise TypeError("document must be a NormalizedDocument")

    decisions: list[BoundaryDecision] = []
    active_question = False
    option_labels: set[str] = set()
    for line, span in zip(document.lines, document.source_map, strict=True):
        text = line.normalized_text
        heading = _section_heading(text)
        numeric_false = _numeric_false_positive(text)
        marker = _marker_parts(text)
        previous_complete = active_question and len(option_labels) >= 2
        option_state = active_question and bool(option_labels)
        evidence = [
            BoundaryEvidence(
                "LINE_START_NUMBER_MARKER", marker is not None, 3 if marker else 0,
                "recognized line-start marker" if marker else "no supported line-start marker",
            ),
            BoundaryEvidence(
                "PREVIOUS_QUESTION_COMPLETENESS", previous_complete, 1 if previous_complete else 0,
                "previous boundary has at least two option labels" if previous_complete else "no completed previous option sequence",
            ),
            BoundaryEvidence(
                "OPTION_SEQUENCE_STATE", option_state, 1 if option_state else 0,
                "active question has observed option labels" if option_state else "no active option sequence",
            ),
            BoundaryEvidence(
                "SECTION_HEADING_SIGNAL", heading, -4 if heading else 0,
                "section or choice-type heading" if heading else "not a recognized section heading",
            ),
            BoundaryEvidence(
                "NUMERIC_FALSE_POSITIVE_SIGNAL", numeric_false, -4 if numeric_false else 0,
                "numeric, measurement, date, page, or anatomical reference" if numeric_false else "not a recognized numeric false positive",
            ),
        ]
        warnings: list[str] = []
        number: int | None = None
        question_marker: str | None = None
        stem_preview: str | None = None
        strength: BoundaryStrength = "NONE"

        if heading:
            warnings.append("section_heading")
        elif numeric_false:
            warnings.append("numeric_false_positive")
        elif marker is not None:
            number, question_marker, stem = marker
            stem, has_type_marker = _stem_after_type_marker(stem)
            plausible = _plausible_stem(stem)
            evidence.append(
                BoundaryEvidence(
                    "PLAUSIBLE_STEM_AFTER_MARKER", plausible, 3 if plausible else 0,
                    "marker is followed by plausible non-numeric text" if plausible else "missing, short, or numeric-only stem",
                )
            )
            stem_preview = stem[:80] if stem else None
            if not stem:
                strength = "WEAK"
                warnings.append("incomplete_marker")
            elif plausible and has_type_marker:
                strength = "STRONG"
            elif plausible and question_marker is not None and question_marker.startswith("("):
                strength = "STRONG"
            elif plausible:
                strength = "MEDIUM"
            else:
                strength = "WEAK"

        is_boundary = strength in {"STRONG", "MEDIUM"}
        decisions.append(
            BoundaryDecision(
                line_number=line.normalized_line_number,
                decision=strength,
                is_boundary=is_boundary,
                question_number=number,
                question_marker=question_marker,
                stem_preview=stem_preview,
                evidence=tuple(evidence),
                warnings=tuple(warnings),
                source_span=span,
            )
        )

        if is_boundary:
            active_question = True
            option_labels = set()
        option = _OPTION_RE.fullmatch(text)
        if active_question and option is not None:
            option_labels.add(option.group("label"))

    return tuple(decisions)


__all__ = ["BoundaryDecision", "BoundaryEvidence", "detect_boundaries"]
