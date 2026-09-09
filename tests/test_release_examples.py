from __future__ import annotations

import json
from pathlib import Path
import struct
import zipfile

from jsonschema import Draft7Validator

from qbassist import ExtractedQuestionBatch, build_question_bank_from_extracted
from qbbank import SourceRecord, deserialize_question_bank, serialize_question_bank
from qbproduction.csv_exporter import serialize_standard_question_bank_csv
from qbproduction.csv_projection import project_question_items_to_csv_rows


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOT = ROOT / "examples" / "basic"
SOURCE_ROOT = EXAMPLE_ROOT / "source"
EXTRACTION_PATH = EXAMPLE_ROOT / "extracted-questions.json"
BANK_PATH = EXAMPLE_ROOT / "question-bank.json"
CSV_PATH = EXAMPLE_ROOT / "standard-question-bank.csv"
SCHEMA_PATH = (
    ROOT
    / "skills"
    / "curate-question-bank"
    / "schemas"
    / "extracted-question-v1.schema.json"
)
SOURCES = [
    SourceRecord(
        "81000000-0000-4000-8000-000000000001",
        "source/questions.md",
        "markdown",
    ),
    SourceRecord(
        "81000000-0000-4000-8000-000000000002",
        "source/question.docx",
        "docx",
    ),
    SourceRecord(
        "81000000-0000-4000-8000-000000000003",
        "source/question.png",
        "image",
    ),
]
GENERATED_IDS = (
    "91000000-0000-4000-8000-000000000001",
    "92000000-0000-4000-8000-000000000001",
    "93000000-0000-4000-8000-000000000001",
    "93000000-0000-4000-8000-000000000002",
    "92000000-0000-4000-8000-000000000002",
    "93000000-0000-4000-8000-000000000003",
    "93000000-0000-4000-8000-000000000004",
    "93000000-0000-4000-8000-000000000005",
    "92000000-0000-4000-8000-000000000003",
)


def _load_extraction() -> dict:
    return json.loads(EXTRACTION_PATH.read_text(encoding="utf-8"))


def _build_example_bank():
    identities = iter(GENERATED_IDS)
    return build_question_bank_from_extracted(
        title="QBC v1.0 入门示例",
        sources=SOURCES,
        batch=ExtractedQuestionBatch.from_dict(_load_extraction()),
        uuid_factory=lambda: next(identities),
    )


def test_example_extraction_validates_and_contains_no_qbc_owned_ids() -> None:
    payload = _load_extraction()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert list(Draft7Validator(schema).iter_errors(payload)) == []
    serialized = json.dumps(payload, ensure_ascii=False)
    for forbidden in (
        "question_id",
        "source_option_id",
        "candidate_id",
        "question_revision",
    ):
        assert forbidden not in serialized
    assert payload["questions"][0]["answer"] is None
    assert payload["questions"][1]["answer"] == ["A", "C"]
    assert payload["questions"][2]["answer"] is False
    assert payload["questions"][2]["options"] == []


def test_example_compiles_to_exact_canonical_json_and_current_csv() -> None:
    bank = _build_example_bank()

    assert serialize_question_bank(bank) == BANK_PATH.read_text(encoding="utf-8")
    assert deserialize_question_bank(BANK_PATH.read_text(encoding="utf-8")) == bank
    assert serialize_standard_question_bank_csv(
        project_question_items_to_csv_rows(bank.questions)
    ) == CSV_PATH.read_text(encoding="utf-8")


def test_markdown_docx_and_png_are_real_small_local_sources() -> None:
    markdown = (SOURCE_ROOT / "questions.md").read_text(encoding="utf-8")
    docx_path = SOURCE_ROOT / "question.docx"
    png_path = SOURCE_ROOT / "question.png"

    assert "正常成人视力通常记录为" in markdown
    assert zipfile.is_zipfile(docx_path)
    with zipfile.ZipFile(docx_path) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
    assert "下列哪些属于脑神经" in document_xml
    assert "视神经" in document_xml and "面神经" in document_xml

    png = png_path.read_bytes()
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", png[16:24])
    assert 300 <= width <= 1600
    assert 150 <= height <= 1200
    assert len(png) < 200_000


def test_example_source_references_resolve_to_all_three_source_concepts() -> None:
    payload = _load_extraction()
    referenced = {
        question["source_reference"]["source_id"]
        for question in payload["questions"]
    }

    assert referenced == {source.source_id for source in SOURCES}
    assert [source.source_type for source in SOURCES] == ["markdown", "docx", "image"]
