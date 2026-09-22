"""Discover and stream monthly AQX_P_488 CSV files."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterator

import pandas as pd

from .constants import MISSING_MARKERS, SOURCE_COLUMNS

MONTH_FILE_RE = re.compile(r"^aqi_(\d{4})_(\d{2})\.csv$", re.IGNORECASE)
UTF8_REPLACEMENT_BYTES = b"\xef\xbf\xbd"


class SourceDataError(ValueError):
    """Raised when a source file cannot be imported safely."""


@dataclass(frozen=True)
class SourceFile:
    path: Path
    month: date
    size_bytes: int

    def sha256(self) -> str:
        digest = hashlib.sha256()
        with self.path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()


def discover_source_files(data_dir: str | Path) -> list[SourceFile]:
    """Return recognized monthly files in chronological order."""
    root = Path(data_dir).expanduser().resolve()
    if not root.is_dir():
        raise SourceDataError(f"Data directory does not exist: {root}")

    files: list[SourceFile] = []
    for path in root.glob("*.csv"):
        match = MONTH_FILE_RE.match(path.name)
        if not match:
            continue
        year, month = (int(part) for part in match.groups())
        try:
            source_month = date(year, month, 1)
        except ValueError as exc:
            raise SourceDataError(f"Invalid month in filename: {path.name}") from exc
        files.append(SourceFile(path=path, month=source_month, size_bytes=path.stat().st_size))

    if not files:
        raise SourceDataError(f"No aqi_YYYY_MM.csv files found in: {root}")
    return sorted(files, key=lambda item: (item.month, item.path.name))


def _validate_source_file(source_file: SourceFile) -> None:
    """Reject schema drift and irreversibly corrupted UTF-8 text."""
    with source_file.path.open("rb") as source:
        header_bytes = source.readline()
        while block := source.read(1024 * 1024):
            if UTF8_REPLACEMENT_BYTES in block:
                raise SourceDataError(
                    f"{source_file.path.name} contains Unicode replacement characters (�). "
                    "The official CSV export damaged Chinese text; rebuild it from the JSON resource."
                )

    try:
        header = header_bytes.decode("utf-8-sig").strip("\r\n").split(",")
    except UnicodeDecodeError as exc:
        raise SourceDataError(f"{source_file.path.name} is not valid UTF-8") from exc

    if tuple(header) != SOURCE_COLUMNS:
        missing = sorted(set(SOURCE_COLUMNS) - set(header))
        extra = sorted(set(header) - set(SOURCE_COLUMNS))
        raise SourceDataError(
            f"Unexpected schema in {source_file.path.name}; missing={missing}, extra={extra}"
        )


def iter_csv_chunks(source_file: SourceFile, chunk_size: int = 50_000) -> Iterator[pd.DataFrame]:
    """Yield normalized raw chunks without loading a whole month into memory."""
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    _validate_source_file(source_file)

    first_data_row = 2
    for chunk in pd.read_csv(
        source_file.path,
        dtype=str,
        chunksize=chunk_size,
        encoding="utf-8-sig",
        keep_default_na=True,
        na_values=list(MISSING_MARKERS),
    ):
        chunk.insert(0, "source_file", source_file.path.name)
        chunk.insert(
            1,
            "source_row_number",
            range(first_data_row, first_data_row + len(chunk)),
        )
        first_data_row += len(chunk)
        yield chunk
