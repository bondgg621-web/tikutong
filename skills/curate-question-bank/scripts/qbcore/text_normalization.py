"""Deterministic text normalization and canonical content fingerprints."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
import unicodedata


MAX_CANONICAL_JSON_DEPTH = 64
_ZERO_WIDTH_CHARACTERS = frozenset({"\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"})


@dataclass(frozen=True)
class SourceSpan:
    """Conservative line-level source location for runtime-only metadata.

    Character offsets remain ``None`` because replacement/removal normalization
    does not preserve a trustworthy one-to-one character mapping.
    """

    source_id: str
    line_start: int
    line_end: int
    char_start: int | None = None
    char_end: int | None = None


@dataclass(frozen=True)
class NormalizedLine:
    """One normalized logical line with the original line retained verbatim."""

    normalized_line_number: int
    original_line_number: int
    raw_text: str
    normalized_text: str
    original_span: SourceSpan
    normalized_span: SourceSpan


@dataclass(frozen=True)
class NormalizationChange:
    """A non-lossy audit entry for a character-level normalization event."""

    kind: str
    original_line_number: int
    raw_text: str
    normalized_text: str


@dataclass(frozen=True)
class NormalizedDocument:
    """Runtime normalization view; it is not a Candidate persistence format."""

    source_id: str
    raw_text: str
    normalized_text: str
    lines: tuple[NormalizedLine, ...]
    source_map: tuple[SourceSpan, ...]
    changes: tuple[NormalizationChange, ...]


def normalize_document(raw_text: str, *, source_id: str) -> NormalizedDocument:
    """Build a reversible-at-document-level, line-mapped normalization view.

    This deliberately preserves every logical line and the complete raw input.
    It only normalizes line endings, removes a leading UTF-8 BOM and recognized
    zero-width format characters, and replaces Unicode whitespace with ASCII
    spaces. It neither guesses OCR characters nor changes parser behavior.
    """

    if type(raw_text) is not str:
        raise TypeError("raw_text must be a string")
    if type(source_id) is not str or not source_id:
        raise ValueError("source_id must be a non-empty string")

    logical_text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    raw_lines = logical_text.split("\n")
    normalized_lines: list[NormalizedLine] = []
    source_map: list[SourceSpan] = []
    changes: list[NormalizationChange] = []

    for line_number, raw_line in enumerate(raw_lines, start=1):
        output: list[str] = []
        for character_index, character in enumerate(raw_line):
            if line_number == 1 and character_index == 0 and character == "\ufeff":
                changes.append(
                    NormalizationChange(
                        "leading_utf8_bom_removed", line_number, character, ""
                    )
                )
                continue
            if character in _ZERO_WIDTH_CHARACTERS:
                changes.append(
                    NormalizationChange(
                        "zero_width_removed", line_number, character, ""
                    )
                )
                continue
            if character != " " and character.isspace():
                changes.append(
                    NormalizationChange(
                        "unicode_whitespace_replaced", line_number, character, " "
                    )
                )
                output.append(" ")
                continue
            output.append(character)

        span = SourceSpan(source_id, line_number, line_number)
        normalized_line = NormalizedLine(
            normalized_line_number=line_number,
            original_line_number=line_number,
            raw_text=raw_line,
            normalized_text="".join(output),
            original_span=span,
            normalized_span=span,
        )
        normalized_lines.append(normalized_line)
        source_map.append(span)

    return NormalizedDocument(
        source_id=source_id,
        raw_text=raw_text,
        normalized_text="\n".join(line.normalized_text for line in normalized_lines),
        lines=tuple(normalized_lines),
        source_map=tuple(source_map),
        changes=tuple(changes),
    )


def normalize_text(value: str) -> str:
    """Return the frozen NFC and Unicode-whitespace fingerprint form."""
    if not isinstance(value, str):
        raise TypeError("text value must be a string")

    normalized = " ".join(unicodedata.normalize("NFC", value).split())
    if not normalized:
        raise ValueError("text value must not be empty after normalization")
    return normalized


def _canonical_json_snapshot(
    value: object,
    active_containers: set[int],
    container_depth: int,
) -> object:
    """Validate and copy exact built-ins without traversing caller data twice."""
    if type(value) is str:
        return value

    if type(value) is list:
        container_id = id(value)
        if container_id in active_containers:
            raise ValueError("canonical JSON value must not contain cycles")
        next_depth = container_depth + 1
        if next_depth > MAX_CANONICAL_JSON_DEPTH:
            raise ValueError(
                f"canonical JSON nesting exceeds maximum depth {MAX_CANONICAL_JSON_DEPTH}"
            )
        active_containers.add(container_id)
        try:
            return [
                _canonical_json_snapshot(item, active_containers, next_depth)
                for item in value
            ]
        finally:
            active_containers.remove(container_id)

    if type(value) is dict:
        container_id = id(value)
        if container_id in active_containers:
            raise ValueError("canonical JSON value must not contain cycles")
        next_depth = container_depth + 1
        if next_depth > MAX_CANONICAL_JSON_DEPTH:
            raise ValueError(
                f"canonical JSON nesting exceeds maximum depth {MAX_CANONICAL_JSON_DEPTH}"
            )
        active_containers.add(container_id)
        try:
            snapshot: dict[str, object] = {}
            for key, item in value.items():
                if type(key) is not str:
                    raise TypeError("canonical JSON object keys must be strings")
                snapshot[key] = _canonical_json_snapshot(
                    item,
                    active_containers,
                    next_depth,
                )
            return snapshot
        finally:
            active_containers.remove(container_id)

    raise TypeError(
        "canonical JSON values must use exact built-in dict, list, and str types"
    )


def canonical_json_bytes(value: object) -> bytes:
    """Encode a stable snapshot of exact built-in dict/list/str values.

    Container subclasses are rejected, and container nesting is limited by
    ``MAX_CANONICAL_JSON_DEPTH`` before the stdlib encoder sees the snapshot.
    """
    snapshot = _canonical_json_snapshot(value, set(), 0)
    serialized = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    try:
        return serialized.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError(
            "canonical JSON strings must contain valid UTF-8 text"
        ) from None


def _sha256_hex(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def normalized_text_fingerprint(value: str) -> str:
    """Hash the UTF-8 bytes of normalized stem or option text."""
    normalized = normalize_text(value)
    try:
        payload = normalized.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("text value must contain valid UTF-8 text") from None
    return _sha256_hex(payload)


def stem_fingerprint(value: str) -> str:
    """Readable alias for a normalized stem-text fingerprint."""
    return normalized_text_fingerprint(value)


def _normalized_options(option_texts: Sequence[str]) -> list[str]:
    if isinstance(option_texts, (str, bytes, bytearray)) or not isinstance(
        option_texts, Sequence
    ):
        raise TypeError("option_texts must be a sequence of strings")
    option_snapshot = [option_text for option_text in option_texts]
    if not option_snapshot:
        raise ValueError("option_texts must not be empty")
    return [normalize_text(option_text) for option_text in option_snapshot]


def option_set_fingerprint(option_texts: Sequence[str]) -> str:
    """Hash normalized options as an order-independent duplicate-preserving set."""
    normalized_options = sorted(_normalized_options(option_texts))
    return _sha256_hex(canonical_json_bytes(normalized_options))


def content_revision_fingerprint(
    stem: str,
    option_texts: Sequence[str],
    *,
    question_type: str = "single_choice",
) -> str:
    """Hash ordered content for the exact built-in ``single_choice`` type."""
    if type(question_type) is not str:
        raise TypeError("question_type must be an exact built-in string")
    if question_type != "single_choice":
        raise ValueError("question_type must be exactly 'single_choice'")

    payload = {
        "question_type": question_type,
        "stem": normalize_text(stem),
        "options": _normalized_options(option_texts),
    }
    return _sha256_hex(canonical_json_bytes(payload))
