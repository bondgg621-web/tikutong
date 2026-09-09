from pathlib import Path

from m1_helpers import fixed_now
from qbcore.capabilities import build_capability_matrix
from qbcore.paths import validate_roots
from qbcore.workspace_contracts import validate_workspace_document


def test_capability_matrix_is_honest_and_network_is_never_attempted(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    policy = validate_roots(input_root, tmp_path / "workspace")
    matrix = build_capability_matrix(policy, now=fixed_now, skill_version="0.1.0")
    statuses = {item["id"]: item["status"] for item in matrix["capabilities"]}
    assert statuses == {
        "directory_discovery": "available", "sha256": "available",
        "text_txt_utf8_bom": "available", "text_markdown_basic": "available",
        "pdf": "unsupported", "docx": "unsupported", "xlsx": "unsupported",
        "pptx": "unsupported", "image_ocr": "unsupported", "zip": "unsupported",
    }
    assert matrix["network"] == {"status": "not_authorized", "attempted": False}
    assert str(tmp_path) not in str(matrix)


def test_capability_order_is_stable(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    policy = validate_roots(input_root, tmp_path / "workspace")
    first = build_capability_matrix(policy, now=fixed_now, skill_version="0.1.0")
    second = build_capability_matrix(policy, now=fixed_now, skill_version="0.1.0")
    assert first == second


def test_capability_matrix_passes_the_stdlib_runtime_contract(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    policy = validate_roots(input_root, tmp_path / "workspace")
    matrix = build_capability_matrix(policy, now=fixed_now, skill_version="0.1.0")
    assert validate_workspace_document("capability-matrix", matrix) == []
