"""Standard CSV serialization and file output for projected question rows."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import Iterable, TextIO

from .csv_projection import (
    STANDARD_QUESTION_BANK_CSV_HEADER,
    StandardQuestionBankRow,
)


def _write_rows(rows: Iterable[StandardQuestionBankRow], output: TextIO) -> None:
    writer = csv.DictWriter(
        output,
        fieldnames=STANDARD_QUESTION_BANK_CSV_HEADER,
        extrasaction="raise",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(row.to_dict())


def serialize_standard_question_bank_csv(
    rows: Iterable[StandardQuestionBankRow],
) -> str:
    """Serialize projected rows as UTF-8-compatible CSV text without a BOM."""
    output = StringIO(newline="")
    _write_rows(rows, output)
    return output.getvalue()


def write_standard_question_bank_csv(
    rows: Iterable[StandardQuestionBankRow],
    output: str | Path | TextIO,
) -> None:
    """Write projected rows to a UTF-8 path or an already-open text stream."""
    if hasattr(output, "write"):
        _write_rows(rows, output)  # type: ignore[arg-type]
        return
    with Path(output).open("w", encoding="utf-8", newline="") as stream:
        _write_rows(rows, stream)
