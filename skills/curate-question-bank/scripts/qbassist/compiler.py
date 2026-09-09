"""QBC-owned first materialization from ExtractedQuestion to QuestionBank v1.0."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from uuid import UUID, uuid4

from qbbank.question_bank import QuestionBank, SourceRecord
from qbbank.validation import QuestionBankValidationError, validate_question_bank
from qbproduction.question_item import QuestionItem

from .extracted_question import (
    ExtractedQuestion,
    ExtractedQuestionBatch,
    validate_extracted_question_batch_mapping,
)


FIRST_MATERIALIZATION_STATUS = "candidate"
EXTRACTION_NOTES_METADATA_KEY = "qbc_extraction_notes"
UuidFactory = Callable[[], UUID | str]


class AssistedIntakeCompilationError(ValueError):
    """Raised when deterministic assisted materialization cannot proceed."""


def build_question_bank_from_extracted(
    *,
    title: str,
    sources: Sequence[SourceRecord],
    batch: ExtractedQuestionBatch,
    uuid_factory: UuidFactory = uuid4,
) -> QuestionBank:
    """Materialize one new canonical bank without content repair or deduplication."""

    if not isinstance(batch, ExtractedQuestionBatch):
        raise AssistedIntakeCompilationError(
            "batch must be an ExtractedQuestionBatch"
        )
    validate_extracted_question_batch_mapping(batch.to_dict())

    source_list = list(sources)
    if not source_list:
        raise AssistedIntakeCompilationError("sources must be non-empty")
    if any(not isinstance(source, SourceRecord) for source in source_list):
        raise AssistedIntakeCompilationError("sources must contain SourceRecord values")
    source_ids = [source.source_id for source in source_list]
    if len(source_ids) != len(set(source_ids)):
        raise AssistedIntakeCompilationError("duplicate source_id")
    known_source_ids = set(source_ids)
    for index, question in enumerate(batch.questions):
        source_id = question.source_reference.source_id
        if source_id not in known_source_ids:
            raise AssistedIntakeCompilationError(
                f"questions[{index}] references unknown source_id: {source_id}"
            )

    generated_ids: set[str] = set()
    bank_id = _next_uuid4(
        uuid_factory, generated_ids=generated_ids, field="bank_id"
    )
    questions = [
        _materialize_question(
            question,
            uuid_factory=uuid_factory,
            generated_ids=generated_ids,
        )
        for question in batch.questions
    ]
    bank = QuestionBank(
        schema_version="1.0",
        bank_id=bank_id,
        title=title,
        questions=questions,
        sources=source_list,
    )
    try:
        validate_question_bank(bank)
    except QuestionBankValidationError as exc:
        raise AssistedIntakeCompilationError(
            f"compiled QuestionBank is invalid: {exc}"
        ) from exc
    return bank


def _materialize_question(
    question: ExtractedQuestion,
    *,
    uuid_factory: UuidFactory,
    generated_ids: set[str],
) -> QuestionItem:
    question_id = _next_uuid4(
        uuid_factory,
        generated_ids=generated_ids,
        field="question_id",
    )
    options = [
        {
            "label": option.label,
            "text": option.text,
            "source_option_id": _next_uuid4(
                uuid_factory,
                generated_ids=generated_ids,
                field="source_option_id",
            ),
        }
        for option in question.options
    ]
    metadata = (
        {EXTRACTION_NOTES_METADATA_KEY: question.extraction_notes}
        if question.extraction_notes is not None
        else None
    )
    answer = list(question.answer) if isinstance(question.answer, list) else question.answer
    return QuestionItem(
        question_id=question_id,
        question_revision=1,
        question_type=question.question_type,
        stem=question.stem,
        options=options,
        source_reference=question.source_reference.to_dict(),
        status=FIRST_MATERIALIZATION_STATUS,
        chapter=question.chapter,
        metadata=metadata,
        answer=answer,
        explanation=question.explanation,
    )


def _next_uuid4(
    uuid_factory: UuidFactory,
    *,
    generated_ids: set[str],
    field: str,
) -> str:
    try:
        value = str(uuid_factory())
        parsed = UUID(value)
    except (StopIteration, TypeError, ValueError, AttributeError) as exc:
        raise AssistedIntakeCompilationError(
            f"{field} factory must return a canonical UUID4"
        ) from exc
    if parsed.version != 4 or value != str(parsed):
        raise AssistedIntakeCompilationError(
            f"{field} factory must return a canonical UUID4"
        )
    if value in generated_ids:
        raise AssistedIntakeCompilationError(
            f"uuid_factory returned duplicate identity: {value}"
        )
    generated_ids.add(value)
    return value
