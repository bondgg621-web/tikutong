"""Pure orchestration from strict source text to Standard Question Bank CSV."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from qbcore.candidate_materializer import materialize_candidates
from qbcore.single_choice_parser import parse_single_choice

from .batch_assembly import assemble_question_items
from .csv_exporter import serialize_standard_question_bank_csv
from .csv_projection import project_question_items_to_csv_rows


class StandardQuestionBankPipelineError(ValueError):
    """Raised when strict source text is not publishable as a question bank."""


def build_standard_question_bank_csv(
    source_text: str,
    *,
    source_id: str,
    uuid_factory: Callable[[], UUID],
) -> str:
    """Run existing pure layers and return CSV text without answer inference."""
    if type(source_text) is not str:
        raise StandardQuestionBankPipelineError("source_text must be a string")

    parse_result = parse_single_choice(source_text)
    if not parse_result.publishable:
        raise StandardQuestionBankPipelineError(
            "source text must contain publishable strict single-choice questions "
            "without parse findings"
        )

    candidate_document = materialize_candidates(
        parse_result.questions,
        source_id=source_id,
        uuid_factory=uuid_factory,
    )
    question_items = assemble_question_items(
        parse_result.questions,
        candidate_document["candidates"],
    )
    rows = project_question_items_to_csv_rows(question_items)
    return serialize_standard_question_bank_csv(rows)


__all__ = ["StandardQuestionBankPipelineError", "build_standard_question_bank_csv"]
