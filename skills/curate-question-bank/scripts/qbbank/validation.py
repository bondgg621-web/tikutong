"""Fail-closed canonical-profile validation for Question Bank v1.0."""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any


UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
WINDOWS_ABSOLUTE_PATTERN = re.compile(r"^[A-Za-z]:[\\/]")

TOP_LEVEL_FIELDS = frozenset(
    {"schema_version", "bank_id", "title", "questions", "sources"}
)
SOURCE_FIELDS = frozenset({"source_id", "source_file", "source_type"})
QUESTION_REQUIRED_FIELDS = frozenset(
    {
        "question_id",
        "question_revision",
        "question_type",
        "stem",
        "options",
        "source_reference",
        "status",
    }
)
QUESTION_OPTIONAL_FIELDS = frozenset(
    {"chapter", "metadata", "answer", "explanation"}
)
OPTION_FIELDS = frozenset({"label", "text", "source_option_id"})
SOURCE_REFERENCE_FIELDS = frozenset({"source_id", "locator"})
SOURCE_TYPES = frozenset({"pdf", "docx", "image", "text", "markdown", "structured"})
QUESTION_TYPES = frozenset({"single_choice", "multiple_choice", "true_false"})
CHOICE_LABELS = frozenset({"A", "B", "C", "D", "E"})


class QuestionBankValidationError(ValueError):
    """Raised when a value is not a valid canonical Question Bank v1.0."""


def _fail(message: str) -> None:
    raise QuestionBankValidationError(message)


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{name} must be an object")
    return value


def _exact_fields(
    value: Mapping[str, Any],
    *,
    allowed: frozenset[str],
    required: frozenset[str],
    name: str,
) -> None:
    unknown = set(value) - allowed
    if unknown:
        _fail(f"unknown field in {name}: {sorted(unknown)[0]}")
    missing = required - set(value)
    if missing:
        _fail(f"missing {name} field: {sorted(missing)[0]}")


def _uuid(value: Any, name: str) -> str:
    if not isinstance(value, str) or UUID_PATTERN.fullmatch(value) is None:
        _fail(f"{name} must be a lowercase UUID")
    return value


def _nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or value == "":
        _fail(f"{name} must be a non-empty string")
    return value


def validate_question_bank_mapping(value: Mapping[str, Any]) -> None:
    """Validate a JSON-like value against the stricter v1.0 canonical profile."""

    bank = _mapping(value, "question bank")
    _exact_fields(
        bank,
        allowed=TOP_LEVEL_FIELDS,
        required=TOP_LEVEL_FIELDS,
        name="question bank",
    )

    if bank["schema_version"] != "1.0":
        _fail("schema_version must be exactly '1.0'")
    _uuid(bank["bank_id"], "bank_id")
    _nonempty_string(bank["title"], "title")

    sources = bank["sources"]
    if not isinstance(sources, list) or not sources:
        _fail("sources must be a non-empty array")
    source_ids: set[str] = set()
    for index, raw_source in enumerate(sources):
        source = _mapping(raw_source, f"sources[{index}]")
        _exact_fields(
            source,
            allowed=SOURCE_FIELDS,
            required=SOURCE_FIELDS,
            name=f"sources[{index}]",
        )
        source_id = _uuid(source["source_id"], f"sources[{index}].source_id")
        if source_id in source_ids:
            _fail(f"duplicate source_id: {source_id}")
        source_ids.add(source_id)
        source_file = _nonempty_string(
            source["source_file"], f"sources[{index}].source_file"
        )
        if (
            source_file.startswith(("/", "\\\\"))
            or WINDOWS_ABSOLUTE_PATTERN.match(source_file)
        ):
            _fail(f"sources[{index}].source_file must be a portable relative path")
        if source["source_type"] not in SOURCE_TYPES:
            _fail(f"sources[{index}].source_type is unsupported")

    questions = bank["questions"]
    if not isinstance(questions, list) or not questions:
        _fail("questions must be a non-empty array")
    question_ids: set[str] = set()
    for index, raw_question in enumerate(questions):
        _validate_question(raw_question, index=index, source_ids=source_ids)
        question_id = raw_question["question_id"]
        if question_id in question_ids:
            _fail(f"duplicate question_id: {question_id}")
        question_ids.add(question_id)


def _validate_question(
    raw_question: Any, *, index: int, source_ids: set[str]
) -> None:
    name = f"questions[{index}]"
    question = _mapping(raw_question, name)
    _exact_fields(
        question,
        allowed=QUESTION_REQUIRED_FIELDS | QUESTION_OPTIONAL_FIELDS,
        required=QUESTION_REQUIRED_FIELDS,
        name=name,
    )
    _uuid(question["question_id"], f"{name}.question_id")
    revision = question["question_revision"]
    if type(revision) is not int or revision < 1:
        _fail(f"{name}.question_revision must be an integer >= 1")

    question_type = question["question_type"]
    if question_type not in QUESTION_TYPES:
        _fail(f"{name}.question_type is unsupported")
    if not isinstance(question["stem"], str):
        _fail(f"{name}.stem must be a string")
    if not isinstance(question["status"], str):
        _fail(f"{name}.status must be a string")
    if "chapter" in question and not isinstance(question["chapter"], str):
        _fail(f"{name}.chapter must be a string")
    if "metadata" in question and not isinstance(question["metadata"], Mapping):
        _fail(f"{name}.metadata must be an object")
    if "explanation" in question and not isinstance(question["explanation"], str):
        _fail(f"{name}.explanation must be a string")

    source_reference = _mapping(question["source_reference"], f"{name}.source_reference")
    missing_reference = SOURCE_REFERENCE_FIELDS - set(source_reference)
    if missing_reference:
        _fail(f"missing source_reference field: {sorted(missing_reference)[0]}")
    source_id = _uuid(source_reference["source_id"], f"{name}.source_reference.source_id")
    if source_id not in source_ids:
        _fail(f"{name}.source_reference has unknown source_id: {source_id}")
    _nonempty_string(source_reference["locator"], f"{name}.source_reference.locator")

    options = question["options"]
    if not isinstance(options, list):
        _fail(f"{name}.options must be an array")
    if question_type == "true_false" and options:
        _fail(f"{name} true_false options must be empty")

    labels: set[str] = set()
    option_ids: set[str] = set()
    for option_index, raw_option in enumerate(options):
        option_name = f"{name}.options[{option_index}]"
        option = _mapping(raw_option, option_name)
        _exact_fields(
            option,
            allowed=OPTION_FIELDS,
            required=OPTION_FIELDS,
            name=option_name,
        )
        label = option["label"]
        if question_type in {"single_choice", "multiple_choice"}:
            if label not in CHOICE_LABELS:
                _fail(f"{option_name} option label must be one of A-E")
            if label in labels:
                _fail(f"duplicate option label in {name}: {label}")
            labels.add(label)
        if not isinstance(option["text"], str):
            _fail(f"{option_name}.text must be a string")
        option_id = _uuid(option["source_option_id"], f"{option_name}.source_option_id")
        if option_id in option_ids:
            _fail(f"duplicate source_option_id in {name}: {option_id}")
        option_ids.add(option_id)


def validate_question_bank(bank: Any) -> None:
    """Validate a QuestionBank-like model through its serialized mapping."""

    to_dict = getattr(bank, "to_dict", None)
    if not callable(to_dict):
        _fail("question bank model must provide to_dict()")
    validate_question_bank_mapping(to_dict())
