"""Fail-closed materialization from parsed text plus persistent Candidate identity."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .question_item import QuestionItem, QuestionOption
from qbcore.single_choice_parser import ParsedOption, ParsedSingleChoice
from qbcore.validation import UUID_PATTERN


class QuestionItemMaterializationError(ValueError):
    """Raised when parsed text and Candidate identity cannot be paired exactly."""


def _canonical_uuid(value: object, *, field: str) -> str:
    if type(value) is not str or UUID_PATTERN.fullmatch(value) is None:
        raise QuestionItemMaterializationError(f"{field} must be a canonical UUID")
    return value


def _nonempty_string(value: object, *, field: str) -> str:
    if type(value) is not str or not value:
        raise QuestionItemMaterializationError(f"{field} must be a non-empty string")
    return value


def _positive_integer(value: object, *, field: str) -> int:
    if type(value) is not int or value < 1:
        raise QuestionItemMaterializationError(f"{field} must be an integer >= 1")
    return value


def materialize_question_item(
    parsed: ParsedSingleChoice,
    candidate: Mapping[str, Any],
) -> QuestionItem:
    """Combine parsed option text with the exact matching Candidate identities."""

    if type(parsed) is not ParsedSingleChoice:
        raise QuestionItemMaterializationError("parsed must be a ParsedSingleChoice")
    if not isinstance(candidate, Mapping):
        raise QuestionItemMaterializationError("candidate must be a mapping")

    candidate_id = _canonical_uuid(candidate.get("candidate_id"), field="candidate_id")
    source_id = _canonical_uuid(candidate.get("source_id"), field="source_id")
    revision = _positive_integer(
        candidate.get("candidate_revision"), field="candidate_revision"
    )
    locator = _nonempty_string(candidate.get("locator"), field="locator")
    stem = _nonempty_string(candidate.get("stem"), field="stem")
    status = _nonempty_string(candidate.get("status"), field="status")
    if candidate.get("question_type") != "single_choice":
        raise QuestionItemMaterializationError(
            "question_type must be single_choice"
        )
    if stem != parsed.stem:
        raise QuestionItemMaterializationError(
            "parsed stem does not match candidate stem"
        )
    if locator != f"line:{parsed.header_line}":
        raise QuestionItemMaterializationError(
            "parsed header locator does not correspond to candidate locator"
        )

    raw_options = candidate.get("options")
    if not isinstance(raw_options, list) or len(raw_options) != len(parsed.options):
        raise QuestionItemMaterializationError(
            "parsed options do not correspond one-to-one with candidate options"
        )

    candidate_by_key: dict[tuple[str, int, str], str] = {}
    option_ids: set[str] = set()
    for index, raw_option in enumerate(raw_options):
        field = f"candidate.options[{index}]"
        if not isinstance(raw_option, Mapping):
            raise QuestionItemMaterializationError(f"{field} must be a mapping")
        option_id = _canonical_uuid(raw_option.get("option_id"), field=f"{field}.option_id")
        if option_id in option_ids:
            raise QuestionItemMaterializationError("option_id values must be unique")
        option_ids.add(option_id)
        if raw_option.get("candidate_id") != candidate_id:
            raise QuestionItemMaterializationError(
                f"{field}.candidate_id must match candidate_id"
            )
        label = _nonempty_string(raw_option.get("source_label"), field=f"{field}.source_label")
        position = _positive_integer(
            raw_option.get("current_position"), field=f"{field}.current_position"
        )
        source_ref = raw_option.get("source_ref")
        if not isinstance(source_ref, Mapping):
            raise QuestionItemMaterializationError(f"{field}.source_ref must be a mapping")
        if source_ref.get("source_id") != source_id:
            raise QuestionItemMaterializationError(
                f"{field}.source_ref.source_id must match source_id"
            )
        option_locator = _nonempty_string(
            source_ref.get("locator"), field=f"{field}.source_ref.locator"
        )
        key = (label, position, option_locator)
        if key in candidate_by_key:
            raise QuestionItemMaterializationError(
                "candidate option correspondence is ambiguous"
            )
        candidate_by_key[key] = option_id

    options: list[QuestionOption] = []
    parsed_keys: set[tuple[str, int, str]] = set()
    for position, parsed_option in enumerate(parsed.options, start=1):
        if type(parsed_option) is not ParsedOption:
            raise QuestionItemMaterializationError(
                "parsed options must contain ParsedOption records"
            )
        key = (
            parsed_option.source_label,
            position,
            f"line:{parsed_option.line}",
        )
        if key in parsed_keys:
            raise QuestionItemMaterializationError(
                "parsed option correspondence is ambiguous"
            )
        parsed_keys.add(key)
        option_id = candidate_by_key.get(key)
        if option_id is None:
            raise QuestionItemMaterializationError(
                "parsed and candidate options do not correspond exactly"
            )
        options.append(
            {
                "label": parsed_option.source_label,
                "text": parsed_option.text,
                "source_option_id": option_id,
            }
        )
    if parsed_keys != set(candidate_by_key):
        raise QuestionItemMaterializationError(
            "parsed and candidate options do not correspond exactly"
        )

    return QuestionItem(
        question_id=candidate_id,
        question_revision=revision,
        question_type="single_choice",
        stem=parsed.stem,
        options=options,
        source_reference={"source_id": source_id, "locator": locator},
        status=status,
    )


__all__ = [
    "QuestionItemMaterializationError",
    "materialize_question_item",
]
