import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "curate-question-bank" / "scripts"))

from qbproduction.export_projection import project_question_item
from qbproduction.question_item import QuestionItem


def test_question_item_projects_without_renaming_or_mutation():
    item = QuestionItem(
        question_id="Q1",
        question_revision=1,
        question_type="single_choice",
        stem="Example",
        options=[
            {"label": "A", "text": "Alpha", "source_option_id": "31000000-0000-4000-8000-000000000001"},
            {"label": "B", "text": "Beta", "source_option_id": "31000000-0000-4000-8000-000000000002"},
        ],
        source_reference={"source": "test"},
        status="validated",
        chapter="Chapter 1",
        metadata={"tag": "demo"},
        answer="B",
        explanation="Because B.",
    )
    before = item.to_dict()

    projection = project_question_item(item)

    assert projection.to_dict() == before
    assert item.to_dict() == before
    assert projection.options is not item.options


def test_export_projection_is_csv_agnostic():
    item = QuestionItem(
        question_id="Q2",
        question_revision=1,
        question_type="single_choice",
        stem="Example 2",
        options=[
            {"label": "A", "text": "Alpha", "source_option_id": "32000000-0000-4000-8000-000000000001"},
            {"label": "B", "text": "Beta", "source_option_id": "32000000-0000-4000-8000-000000000002"},
        ],
        source_reference={"source": "test"},
        status="validated",
    )

    data = project_question_item(item).to_dict()

    assert "global_index" not in data
    assert "paper_section" not in data
    assert "correct_answer" not in data
    assert "csv" not in data
