"""Pure QuestionItem export projection.

The export projection preserves QuestionItem semantic field names and values.
CSV-specific renaming, flattening, serialization, ordering, and file I/O belong
to the separate CSV adapter layer.
"""

from dataclasses import dataclass
from typing import Any

from .question_item import QuestionItem


@dataclass(frozen=True)
class ExportQuestionProjection:
    question_id: str
    question_revision: int
    question_type: str
    stem: str
    options: list[dict[str, str]]
    source_reference: dict[str, Any]
    status: str
    chapter: str | None = None
    metadata: dict[str, Any] | None = None
    answer: Any = None
    explanation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        value = {
            "question_id": self.question_id,
            "question_revision": self.question_revision,
            "question_type": self.question_type,
            "stem": self.stem,
            "options": [dict(option) for option in self.options],
            "source_reference": dict(self.source_reference),
            "status": self.status,
        }
        if self.chapter is not None:
            value["chapter"] = self.chapter
        if self.metadata is not None:
            value["metadata"] = dict(self.metadata)
        if self.answer is not None:
            value["answer"] = self.answer
        if self.explanation is not None:
            value["explanation"] = self.explanation
        return value


def project_question_item(item: QuestionItem) -> ExportQuestionProjection:
    """Project one QuestionItem without mutation, CSV serialization, or I/O."""
    return ExportQuestionProjection(
        question_id=item.question_id,
        question_revision=item.question_revision,
        question_type=item.question_type,
        stem=item.stem,
        options=[dict(option) for option in item.options],
        source_reference=dict(item.source_reference),
        status=item.status,
        chapter=item.chapter,
        metadata=None if item.metadata is None else dict(item.metadata),
        answer=item.answer,
        explanation=item.explanation,
    )
