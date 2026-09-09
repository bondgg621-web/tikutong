"""Runtime QuestionItem model.

This module provides a minimal canonical object layer corresponding to
question-item.schema.json. It does not perform parsing or export.
"""

from dataclasses import dataclass
from typing import Any, TypedDict


class QuestionOption(TypedDict):
    label: str
    text: str
    source_option_id: str


@dataclass
class QuestionItem:
    question_id: str
    question_revision: int
    question_type: str
    stem: str
    options: list[QuestionOption]
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
