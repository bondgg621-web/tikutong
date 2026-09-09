"""In-memory model for the QBC Canonical Question Bank v1.0 contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from qbproduction.question_item import QuestionItem

from .validation import validate_question_bank_mapping


@dataclass(frozen=True)
class SourceRecord:
    """A source referenced by one or more canonical questions."""

    source_id: str
    source_file: str
    source_type: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> SourceRecord:
        return cls(
            source_id=value["source_id"],
            source_file=value["source_file"],
            source_type=value["source_type"],
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "source_id": self.source_id,
            "source_file": self.source_file,
            "source_type": self.source_type,
        }


@dataclass
class QuestionBank:
    """A complete v1.0 bank that reuses the accepted QuestionItem model."""

    schema_version: str
    bank_id: str
    title: str
    questions: list[QuestionItem]
    sources: list[SourceRecord]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> QuestionBank:
        validate_question_bank_mapping(value)
        questions = [_question_item_from_dict(item) for item in value["questions"]]
        sources = [SourceRecord.from_dict(item) for item in value["sources"]]
        return cls(
            schema_version=value["schema_version"],
            bank_id=value["bank_id"],
            title=value["title"],
            questions=questions,
            sources=sources,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "bank_id": self.bank_id,
            "title": self.title,
            "questions": [question.to_dict() for question in self.questions],
            "sources": [source.to_dict() for source in self.sources],
        }


def _question_item_from_dict(value: Mapping[str, Any]) -> QuestionItem:
    optional = {
        key: value[key]
        for key in ("chapter", "metadata", "answer", "explanation")
        if key in value
    }
    return QuestionItem(
        question_id=value["question_id"],
        question_revision=value["question_revision"],
        question_type=value["question_type"],
        stem=value["stem"],
        options=[dict(option) for option in value["options"]],
        source_reference=dict(value["source_reference"]),
        status=value["status"],
        **optional,
    )
