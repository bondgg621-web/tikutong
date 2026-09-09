"""Pure Standard Question Bank CSV row projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .question_item import QuestionItem


STANDARD_QUESTION_BANK_CSV_HEADER = (
    "全局序号",
    "试卷/章节",
    "题型",
    "题干",
    "A",
    "B",
    "C",
    "D",
    "E",
    "正确答案",
    "解析",
)

QUESTION_TYPE_MAPPING = {
    "single_choice": "单选题",
    "multiple_choice": "多选题",
    "true_false": "判断题",
}

_OPTION_LABELS = ("A", "B", "C", "D", "E")
_OPTION_LABEL_SET = frozenset(_OPTION_LABELS)
_MULTIPLE_CHOICE_SEPARATORS = frozenset({" ", "\t", "\r", "\n", ",", ";", "|", "/"})
_TRUE_ANSWERS = frozenset({"true", "t", "正确", "对"})
_FALSE_ANSWERS = frozenset({"false", "f", "错误", "错"})


@dataclass(frozen=True)
class StandardQuestionBankRow:
    sequence_number: int
    paper_or_chapter: str
    question_type: str
    stem: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    option_e: str
    correct_answer: str
    explanation: str

    def to_dict(self) -> dict[str, int | str]:
        """Return the exact 11-column external row contract in header order."""
        return {
            "全局序号": self.sequence_number,
            "试卷/章节": self.paper_or_chapter,
            "题型": self.question_type,
            "题干": self.stem,
            "A": self.option_a,
            "B": self.option_b,
            "C": self.option_c,
            "D": self.option_d,
            "E": self.option_e,
            "正确答案": self.correct_answer,
            "解析": self.explanation,
        }


def _normalize_option_label(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("option label must be a string in A-E")
    label = value.strip().upper()
    if label not in _OPTION_LABEL_SET:
        raise ValueError(f"unsupported option label: {value!r}")
    return label


def _project_options(options: list[dict[str, str]]) -> dict[str, str]:
    projected = {label: "" for label in _OPTION_LABELS}
    seen: set[str] = set()
    for option in options:
        label = _normalize_option_label(option.get("label"))
        if label in seen:
            raise ValueError(f"duplicate option label: {label}")
        seen.add(label)
        text = option.get("text")
        if not isinstance(text, str):
            raise ValueError(f"option {label} text must be a string")
        projected[label] = text
    return projected


def _normalize_choice_label(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("choice answer labels must be strings")
    label = value.strip().upper()
    if label not in _OPTION_LABEL_SET:
        raise ValueError(f"unsupported choice answer: {value!r}")
    return label


def _normalize_multiple_choice_answer(answer: Any) -> str:
    if isinstance(answer, str):
        compact = "".join(
            character
            for character in answer.upper()
            if character not in _MULTIPLE_CHOICE_SEPARATORS
        )
        labels = list(compact)
    elif isinstance(answer, (list, tuple, set, frozenset)):
        labels = [_normalize_choice_label(value) for value in answer]
    else:
        raise ValueError("multiple_choice answer must be labels or a label string")

    if not labels or any(label not in _OPTION_LABEL_SET for label in labels):
        raise ValueError(f"unsupported multiple_choice answer: {answer!r}")
    return "".join(label for label in _OPTION_LABELS if label in set(labels))


def _normalize_true_false_answer(answer: Any) -> str:
    if answer is True:
        return "正确"
    if answer is False:
        return "错误"
    if isinstance(answer, str):
        normalized = answer.strip().casefold()
        if normalized in _TRUE_ANSWERS:
            return "正确"
        if normalized in _FALSE_ANSWERS:
            return "错误"
    raise ValueError(f"unsupported true_false answer: {answer!r}")


def _normalize_answer(question_type: str, answer: Any) -> str:
    if answer is None:
        return ""
    if question_type == "single_choice":
        return _normalize_choice_label(answer)
    if question_type == "multiple_choice":
        return _normalize_multiple_choice_answer(answer)
    if question_type == "true_false":
        return _normalize_true_false_answer(answer)
    raise ValueError(f"unsupported question_type: {question_type!r}")


def project_question_item_to_csv_row(
    question_item: QuestionItem,
    sequence_number: int,
) -> StandardQuestionBankRow:
    """Project one QuestionItem without mutating it or performing file I/O."""
    if not isinstance(sequence_number, int) or isinstance(sequence_number, bool) or sequence_number < 1:
        raise ValueError("sequence_number must be an integer greater than or equal to 1")
    try:
        external_question_type = QUESTION_TYPE_MAPPING[question_item.question_type]
    except KeyError as error:
        raise ValueError(
            f"unsupported question_type: {question_item.question_type!r}"
        ) from error

    options = _project_options(question_item.options)
    return StandardQuestionBankRow(
        sequence_number=sequence_number,
        paper_or_chapter=question_item.chapter if question_item.chapter is not None else "",
        question_type=external_question_type,
        stem=question_item.stem,
        option_a=options["A"],
        option_b=options["B"],
        option_c=options["C"],
        option_d=options["D"],
        option_e=options["E"],
        correct_answer=_normalize_answer(question_item.question_type, question_item.answer),
        explanation=question_item.explanation if question_item.explanation is not None else "",
    )


def project_question_items_to_csv_rows(
    question_items: Iterable[QuestionItem],
) -> list[StandardQuestionBankRow]:
    """Project a batch with deterministic one-based sequence numbering."""
    return [
        project_question_item_to_csv_row(item, sequence_number)
        for sequence_number, item in enumerate(question_items, start=1)
    ]
