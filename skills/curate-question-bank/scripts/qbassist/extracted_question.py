"""Content-only extraction model and fail-closed validation for assisted intake."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re
from typing import Any


UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
QUESTION_TYPES = frozenset({"single_choice", "multiple_choice", "true_false"})
CHOICE_LABELS = frozenset({"A", "B", "C", "D", "E"})
BATCH_FIELDS = frozenset({"questions"})
QUESTION_REQUIRED_FIELDS = frozenset(
    {"question_type", "stem", "options", "source_reference"}
)
QUESTION_OPTIONAL_FIELDS = frozenset(
    {"answer", "explanation", "chapter", "extraction_notes"}
)
OPTION_FIELDS = frozenset({"label", "text"})
SOURCE_REFERENCE_FIELDS = frozenset({"source_id", "locator"})


class ExtractedQuestionValidationError(ValueError):
    """Raised when an extraction payload violates the v1 content contract."""


def _fail(message: str) -> None:
    raise ExtractedQuestionValidationError(message)


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


def _nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{name} must be a non-empty string")
    return value


def _optional_string(value: Any, name: str) -> str | None:
    if value is not None and not isinstance(value, str):
        _fail(f"{name} must be a string or null")
    return value


def _uuid(value: Any, name: str) -> str:
    if not isinstance(value, str) or UUID_PATTERN.fullmatch(value) is None:
        _fail(f"{name} must be a lowercase UUID")
    return value


def validate_extracted_question_batch_mapping(value: Mapping[str, Any]) -> None:
    """Validate one content-only extraction batch without repairing it."""

    batch = _mapping(value, "extraction batch")
    _exact_fields(
        batch,
        allowed=BATCH_FIELDS,
        required=BATCH_FIELDS,
        name="extraction batch",
    )
    questions = batch["questions"]
    if not isinstance(questions, list) or not questions:
        _fail("questions must be a non-empty array")
    for index, question in enumerate(questions):
        _validate_question(question, index=index)


def _validate_question(raw_question: Any, *, index: int) -> None:
    name = f"questions[{index}]"
    question = _mapping(raw_question, name)
    _exact_fields(
        question,
        allowed=QUESTION_REQUIRED_FIELDS | QUESTION_OPTIONAL_FIELDS,
        required=QUESTION_REQUIRED_FIELDS,
        name=name,
    )

    question_type = question["question_type"]
    if not isinstance(question_type, str) or question_type not in QUESTION_TYPES:
        _fail(f"{name}.question_type is unsupported")
    _nonempty_string(question["stem"], f"{name}.stem")

    source_reference = _mapping(
        question["source_reference"], f"{name}.source_reference"
    )
    _exact_fields(
        source_reference,
        allowed=SOURCE_REFERENCE_FIELDS,
        required=SOURCE_REFERENCE_FIELDS,
        name=f"{name}.source_reference",
    )
    _uuid(source_reference["source_id"], f"{name}.source_reference.source_id")
    _nonempty_string(
        source_reference["locator"], f"{name}.source_reference.locator"
    )

    for field in ("explanation", "chapter", "extraction_notes"):
        if field in question:
            _optional_string(question[field], f"{name}.{field}")

    options = question["options"]
    if not isinstance(options, list):
        _fail(f"{name}.options must be an array")
    if question_type == "true_false":
        if options:
            _fail(f"{name} true_false options must be empty")
        _validate_true_false_answer(question.get("answer"), name=name)
        return

    if not 2 <= len(options) <= 5:
        _fail(f"{name}.options must contain 2-5 options")
    labels: set[str] = set()
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
        if not isinstance(label, str) or label not in CHOICE_LABELS:
            _fail(f"{option_name} option label must be one of A-E")
        if label in labels:
            _fail(f"duplicate option label in {name}: {label}")
        labels.add(label)
        _nonempty_string(option["text"], f"{option_name} option text")

    answer = question.get("answer")
    if question_type == "single_choice":
        _validate_single_choice_answer(answer, labels=labels, name=name)
    else:
        _validate_multiple_choice_answer(answer, labels=labels, name=name)


def _validate_single_choice_answer(
    answer: Any, *, labels: set[str], name: str
) -> None:
    if answer is None:
        return
    if not isinstance(answer, str) or answer not in labels:
        _fail(f"{name}.answer must be one existing option label or null")


def _validate_multiple_choice_answer(
    answer: Any, *, labels: set[str], name: str
) -> None:
    if answer is None:
        return
    if not isinstance(answer, list):
        _fail(f"{name}.answer must be an array of option labels or null")
    if len(answer) < 2:
        _fail(f"{name}.answer must contain at least two labels")
    if any(not isinstance(label, str) for label in answer):
        _fail(f"{name}.answer labels must be strings")
    if len(set(answer)) != len(answer):
        _fail(f"{name}.answer contains duplicate labels")
    if any(label not in labels for label in answer):
        _fail(f"{name}.answer references a missing option label")


def _validate_true_false_answer(answer: Any, *, name: str) -> None:
    if answer is not None and type(answer) is not bool:
        _fail(f"{name}.answer must be boolean or null")


@dataclass(frozen=True)
class ExtractedOption:
    label: str
    text: str

    def to_dict(self) -> dict[str, str]:
        return {"label": self.label, "text": self.text}


@dataclass(frozen=True)
class ExtractedSourceReference:
    source_id: str
    locator: str

    def to_dict(self) -> dict[str, str]:
        return {"source_id": self.source_id, "locator": self.locator}


@dataclass(frozen=True)
class ExtractedQuestion:
    question_type: str
    stem: str
    options: list[ExtractedOption]
    answer: Any
    explanation: str | None
    chapter: str | None
    source_reference: ExtractedSourceReference
    extraction_notes: str | None

    @classmethod
    def _from_validated_dict(cls, value: Mapping[str, Any]) -> ExtractedQuestion:
        reference = value["source_reference"]
        return cls(
            question_type=value["question_type"],
            stem=value["stem"],
            options=[
                ExtractedOption(label=option["label"], text=option["text"])
                for option in value["options"]
            ],
            answer=value.get("answer"),
            explanation=value.get("explanation"),
            chapter=value.get("chapter"),
            source_reference=ExtractedSourceReference(
                source_id=reference["source_id"], locator=reference["locator"]
            ),
            extraction_notes=value.get("extraction_notes"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_type": self.question_type,
            "stem": self.stem,
            "options": [option.to_dict() for option in self.options],
            "answer": self.answer,
            "explanation": self.explanation,
            "chapter": self.chapter,
            "source_reference": self.source_reference.to_dict(),
            "extraction_notes": self.extraction_notes,
        }


@dataclass(frozen=True)
class ExtractedQuestionBatch:
    questions: list[ExtractedQuestion]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ExtractedQuestionBatch:
        validate_extracted_question_batch_mapping(value)
        return cls(
            questions=[
                ExtractedQuestion._from_validated_dict(question)
                for question in value["questions"]
            ]
        )

    def to_dict(self) -> dict[str, Any]:
        return {"questions": [question.to_dict() for question in self.questions]}
