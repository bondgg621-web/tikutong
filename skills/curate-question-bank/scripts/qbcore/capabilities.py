from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import platform

from qbcore.paths import RootPolicy


CAPABILITIES = (
    ("directory_discovery", "available", "stdlib recursive discovery"),
    ("sha256", "available", "stdlib hashlib SHA-256"),
    ("text_txt_utf8_bom", "available", "built-in text milestone scope"),
    ("text_markdown_basic", "available", "built-in text milestone scope"),
    ("pdf", "unsupported", "no PDF adapter in Milestone 1"),
    ("docx", "unsupported", "no DOCX adapter in Milestone 1"),
    ("xlsx", "unsupported", "no XLSX adapter in Milestone 1"),
    ("pptx", "unsupported", "no PPTX adapter in Milestone 1"),
    ("image_ocr", "unsupported", "no OCR adapter in Milestone 1"),
    ("zip", "unsupported", "no ZIP adapter in Milestone 1"),
)


def _utc_z(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("clock must return a timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_capability_matrix(
    policy: RootPolicy,
    *,
    now: Callable[[], datetime],
    skill_version: str,
) -> dict:
    return {
        "schema_version": "1.0",
        "generated_at": _utc_z(now()),
        "skill_version": skill_version,
        "python_version": platform.python_version(),
        "input_root_fingerprint": policy.input_fingerprint,
        "workspace_root_fingerprint": policy.workspace_fingerprint,
        "network": {"status": "not_authorized", "attempted": False},
        "capabilities": [
            {"id": identifier, "status": status, "detail": detail}
            for identifier, status, detail in CAPABILITIES
        ],
    }
