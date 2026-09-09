"""Pure first materialization of parsed single-choice candidates."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
import re
from uuid import UUID

from qbcore.single_choice_parser import ParsedOption, ParsedSingleChoice
from qbcore.text_normalization import (
    content_revision_fingerprint,
    normalized_text_fingerprint,
    option_set_fingerprint,
    stem_fingerprint,
)
from qbcore.validation import UUID_PATTERN, validate_document


_DISPLAY_NUMBER_PATTERN = re.compile(r"^[1-9][0-9]*$")


class CandidateMaterializationError(ValueError):
    """Raised when parsed records cannot be materialized safely."""


def _validate_source_id(source_id: str) -> None:
    if type(source_id) is not str or UUID_PATTERN.fullmatch(source_id) is None:
        raise CandidateMaterializationError(
            "source_id must be a canonical lowercase UUID with an eligible version and variant"
        )


def _positive_line(value: object, *, field: str) -> int:
    if type(value) is not int or value < 1:
        raise CandidateMaterializationError(f"{field} must be a positive integer")
    return value


def _snapshot_and_preflight(
    parsed_questions: Iterable[ParsedSingleChoice],
) -> tuple[
    tuple[ParsedSingleChoice, ...],
    tuple[tuple[str, str, str, tuple[str, ...]], ...],
]:
    try:
        questions = tuple(parsed_questions)
    except Exception as exc:
        raise CandidateMaterializationError(
            "parsed_questions must be a finite iterable of ParsedSingleChoice records"
        ) from exc
    if not questions:
        raise CandidateMaterializationError("parsed_questions must not be empty")

    indexed_questions = tuple(enumerate(questions))

    def header_sort_key(indexed_question: tuple[int, object]) -> int:
        original_index, question = indexed_question
        context = f"parsed_questions[{original_index}]"
        if type(question) is not ParsedSingleChoice:
            raise CandidateMaterializationError(
                f"{context} must be a ParsedSingleChoice record"
            )
        return _positive_line(question.header_line, field=f"{context}.header_line")

    indexed_questions = tuple(sorted(indexed_questions, key=header_sort_key))
    questions = tuple(question for _, question in indexed_questions)

    candidate_lines: set[int] = set()
    global_locator_lines: set[int] = set()
    for original_index, question in indexed_questions:
        context = f"parsed_questions[{original_index}]"
        header_line = question.header_line
        if header_line in candidate_lines:
            raise CandidateMaterializationError(
                f"duplicate candidate locator line:{header_line}"
            )
        candidate_lines.add(header_line)
        global_locator_lines.add(header_line)

    computed: list[tuple[str, str, str, tuple[str, ...]]] = []
    last_option_lines: list[int] = []
    for original_index, question in indexed_questions:
        context = f"parsed_questions[{original_index}]"
        if (
            type(question.display_number) is not str
            or _DISPLAY_NUMBER_PATTERN.fullmatch(question.display_number) is None
        ):
            raise CandidateMaterializationError(
                f"{context}.display_number must be a positive decimal string"
            )
        if type(question.stem) is not str:
            raise CandidateMaterializationError(f"{context}.stem must be a string")
        header_line = _positive_line(
            question.header_line, field=f"{context}.header_line"
        )

        if type(question.options) is not tuple:
            raise CandidateMaterializationError(f"{context}.options must be a tuple")
        if len(question.options) < 2:
            raise CandidateMaterializationError(
                f"{context}.options must contain at least two options"
            )
        if len(question.options) > 26:
            raise CandidateMaterializationError(
                f"{context}.options must contain no more than 26 options"
            )

        option_lines: set[int] = set()
        option_texts: list[str] = []
        option_fingerprints: list[str] = []
        previous_line = header_line
        for option_index, option in enumerate(question.options):
            option_context = f"{context}.options[{option_index}]"
            if type(option) is not ParsedOption:
                raise CandidateMaterializationError(
                    f"{option_context} must be a ParsedOption record"
                )
            expected_label = chr(ord("A") + option_index)
            if type(option.source_label) is not str or option.source_label != expected_label:
                raise CandidateMaterializationError(
                    f"{option_context}.source_label must be contiguous label {expected_label}"
                )
            if type(option.text) is not str:
                raise CandidateMaterializationError(
                    f"{option_context}.text must be a string"
                )
            option_line = _positive_line(option.line, field=f"{option_context}.line")
            if option_line in option_lines:
                raise CandidateMaterializationError(
                    f"duplicate option locator line:{option_line} in {context}"
                )
            if option_line <= previous_line:
                raise CandidateMaterializationError(
                    f"{option_context}.line must follow the header and preceding option"
                )
            if option_line in global_locator_lines:
                raise CandidateMaterializationError(
                    f"duplicate source locator line:{option_line}"
                )
            option_lines.add(option_line)
            global_locator_lines.add(option_line)
            previous_line = option_line
            option_texts.append(option.text)
            try:
                option_fingerprints.append(normalized_text_fingerprint(option.text))
            except (TypeError, ValueError) as exc:
                raise CandidateMaterializationError(
                    f"{option_context}.text is not valid materializable text"
                ) from exc

        try:
            computed.append(
                (
                    stem_fingerprint(question.stem),
                    option_set_fingerprint(option_texts),
                    content_revision_fingerprint(question.stem, option_texts),
                    tuple(option_fingerprints),
                )
            )
        except (TypeError, ValueError) as exc:
            raise CandidateMaterializationError(
                f"{context} contains invalid materializable text"
            ) from exc
        last_option_lines.append(previous_line)

    for question_index, last_option_line in enumerate(last_option_lines[:-1]):
        next_header_line = questions[question_index + 1].header_line
        if last_option_line >= next_header_line:
            raise CandidateMaterializationError(
                f"option locator line:{last_option_line} must be before next "
                f"candidate locator line:{next_header_line}"
            )

    return questions, tuple(computed)


def _allocate_uuid(
    uuid_factory: Callable[[], UUID],
    allocated: set[str],
) -> str:
    try:
        value = uuid_factory()
    except StopIteration as exc:
        raise CandidateMaterializationError("uuid_factory exhausted") from exc
    except Exception as exc:
        raise CandidateMaterializationError(
            "uuid_factory raised an exception"
        ) from exc

    if type(value) is not UUID:
        raise CandidateMaterializationError(
            "uuid_factory returned a value that is not an exact UUID object"
        )
    uuid_text = str(value)
    if UUID_PATTERN.fullmatch(uuid_text) is None:
        raise CandidateMaterializationError(
            "uuid_factory returned a UUID with an ineligible version or variant"
        )
    if uuid_text in allocated:
        raise CandidateMaterializationError(
            "uuid_factory returned a duplicate UUID; allocated IDs include source_id"
        )
    allocated.add(uuid_text)
    return uuid_text


def materialize_candidates(
    parsed_questions: Iterable[ParsedSingleChoice],
    *,
    source_id: str,
    uuid_factory: Callable[[], UUID],
) -> dict:
    """Materialize parsed records without I/O or answer handling."""

    _validate_source_id(source_id)
    if not callable(uuid_factory):
        raise CandidateMaterializationError("uuid_factory must be callable")
    questions, computed = _snapshot_and_preflight(parsed_questions)
    revision_counts = Counter(fingerprints[2] for fingerprints in computed)

    allocated: set[str] = {source_id}
    candidates: list[dict] = []
    for question, fingerprints in zip(questions, computed, strict=True):
        stem_hash, option_set_hash, revision_hash, option_hashes = fingerprints
        candidate_id = _allocate_uuid(uuid_factory, allocated)
        options: list[dict] = []
        for position, (parsed_option, option_hash) in enumerate(
            zip(question.options, option_hashes, strict=True), start=1
        ):
            options.append(
                {
                    "option_id": _allocate_uuid(uuid_factory, allocated),
                    "candidate_id": candidate_id,
                    "option_revision": 1,
                    "normalized_text_fingerprint": option_hash,
                    "current_position": position,
                    "source_label": parsed_option.source_label,
                    "source_ref": {
                        "source_id": source_id,
                        "locator": f"line:{parsed_option.line}",
                    },
                    "previous_labels": [],
                }
            )
        candidates.append(
            {
                "candidate_id": candidate_id,
                "candidate_revision": 1,
                "source_id": source_id,
                "locator": f"line:{question.header_line}",
                "question_type": "single_choice",
                "status": "candidate",
                "stem": question.stem,
                "fingerprints": {
                    "stem_fingerprint": stem_hash,
                    "option_set_fingerprint": option_set_hash,
                    "content_revision_fingerprint": revision_hash,
                },
                "options": options,
                "duplicate_group": (
                    f"content-sha256:{revision_hash}"
                    if revision_counts[revision_hash] > 1
                    else None
                ),
            }
        )

    document = {"schema_version": "1.0", "candidates": candidates}
    issues = validate_document("candidate", document)
    if issues:
        details = "; ".join(
            f"{issue.code} at {issue.path}: {issue.message}" for issue in issues
        )
        raise CandidateMaterializationError(
            f"candidate validation failed: {details}"
        )
    return document


__all__ = ["CandidateMaterializationError", "materialize_candidates"]
