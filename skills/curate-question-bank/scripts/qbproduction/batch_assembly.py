"""Fail-closed batch pairing for parsed questions and Candidate records."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from qbcore.single_choice_parser import ParsedSingleChoice

from .question_item import QuestionItem
from .question_item_materializer import (
    QuestionItemMaterializationError,
    materialize_question_item,
)


class BatchQuestionItemAssemblyError(ValueError):
    """Raised when parsed questions and Candidates are not exactly one-to-one."""


def _snapshot(values: Iterable[Any], *, name: str) -> tuple[Any, ...]:
    try:
        return tuple(values)
    except Exception as error:
        raise BatchQuestionItemAssemblyError(
            f"{name} must be a finite iterable"
        ) from error


def _parsed_locator(parsed: object, *, index: int) -> str:
    if type(parsed) is not ParsedSingleChoice:
        raise BatchQuestionItemAssemblyError(
            f"parsed_questions[{index}] must be a ParsedSingleChoice"
        )
    if type(parsed.header_line) is not int or parsed.header_line < 1:
        raise BatchQuestionItemAssemblyError(
            f"parsed_questions[{index}].header_line must be an integer >= 1"
        )
    return f"line:{parsed.header_line}"


def _candidate_locator(candidate: object, *, index: int) -> str:
    if not isinstance(candidate, Mapping):
        raise BatchQuestionItemAssemblyError(
            f"candidates[{index}] must be a mapping"
        )
    locator = candidate.get("locator")
    if type(locator) is not str or not locator:
        raise BatchQuestionItemAssemblyError(
            f"candidates[{index}].locator must be a non-empty string"
        )
    return locator


def assemble_question_items(
    parsed_questions: Iterable[ParsedSingleChoice],
    candidates: Iterable[Mapping[str, Any]],
) -> list[QuestionItem]:
    """Pair by exact header locator and preserve parsed-question input order."""
    parsed_snapshot = _snapshot(parsed_questions, name="parsed_questions")
    candidate_snapshot = _snapshot(candidates, name="candidates")

    candidates_by_locator: dict[str, Mapping[str, Any]] = {}
    for index, candidate in enumerate(candidate_snapshot):
        locator = _candidate_locator(candidate, index=index)
        if locator in candidates_by_locator:
            raise BatchQuestionItemAssemblyError(
                f"duplicate Candidate locator: {locator}"
            )
        candidates_by_locator[locator] = candidate

    parsed_locators: set[str] = set()
    items: list[QuestionItem] = []
    for index, parsed in enumerate(parsed_snapshot):
        locator = _parsed_locator(parsed, index=index)
        if locator in parsed_locators:
            raise BatchQuestionItemAssemblyError(
                f"duplicate ParsedSingleChoice locator: {locator}"
            )
        parsed_locators.add(locator)
        candidate = candidates_by_locator.pop(locator, None)
        if candidate is None:
            raise BatchQuestionItemAssemblyError(
                f"missing Candidate for ParsedSingleChoice locator: {locator}"
            )
        try:
            items.append(materialize_question_item(parsed, candidate))
        except QuestionItemMaterializationError as error:
            raise BatchQuestionItemAssemblyError(
                f"invalid parsed/Candidate pair at {locator}: {error}"
            ) from error

    if candidates_by_locator:
        unmatched = ", ".join(sorted(candidates_by_locator))
        raise BatchQuestionItemAssemblyError(
            f"missing ParsedSingleChoice for Candidate locator(s): {unmatched}"
        )
    return items


__all__ = ["BatchQuestionItemAssemblyError", "assemble_question_items"]
