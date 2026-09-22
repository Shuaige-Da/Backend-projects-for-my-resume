"""Command-line entry point for validating and loading AQX_P_488 files."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path

import database
from src.aqi import (
    SourceDataError,
    discover_source_files,
    iter_csv_chunks,
    transform_air_quality_chunk,
)
from src.aqi.load import complete_import, fail_import, load_chunk, register_import

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "AQX_P_488_Resource"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate or load AQX_P_488 files.")
    parser.add_argument(
        "--mode",
        choices=("validate", "load"),
        default="validate",
        help="validate reads files only; load writes to PostgreSQL.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.getenv("AQI_DATA_DIR", DEFAULT_DATA_DIR)),
        help="Directory containing aqi_YYYY_MM.csv files.",
    )
    parser.add_argument("--chunk-size", type=int, default=50_000)
    parser.add_argument("--limit-files", type=int, default=None)
    return parser.parse_args()


def validate_files(data_dir: Path, chunk_size: int, limit_files: int | None) -> dict:
    files = discover_source_files(data_dir)
    if limit_files is not None:
        files = files[:limit_files]

    summary = {
        "data_dir": str(data_dir.resolve()),
        "files_discovered": len(files),
        "files_valid": 0,
        "files_invalid": 0,
        "rows_accepted": 0,
        "rows_rejected": 0,
        "rejection_reasons": {},
        "quality_flags": {},
        "errors": [],
    }
    rejection_counts: Counter[str] = Counter()
    quality_counts: Counter[str] = Counter()
    for source_file in files:
        try:
            file_accepted = 0
            file_rejected = 0
            for chunk in iter_csv_chunks(source_file, chunk_size):
                result = transform_air_quality_chunk(chunk)
                file_accepted += len(result.accepted)
                file_rejected += len(result.rejected)
                for value in result.rejected.get("rejection_reason", []):
                    rejection_counts.update(str(value).split("|"))
                for value in result.accepted["quality_flags"].dropna():
                    quality_counts.update(str(value).split("|"))
            summary["files_valid"] += 1
            summary["rows_accepted"] += file_accepted
            summary["rows_rejected"] += file_rejected
        except SourceDataError as exc:
            summary["files_invalid"] += 1
            summary["errors"].append(str(exc))
    summary["rejection_reasons"] = dict(rejection_counts.most_common())
    summary["quality_flags"] = dict(quality_counts.most_common())
    return summary


def load_files(data_dir: Path, chunk_size: int, limit_files: int | None) -> dict:
    files = discover_source_files(data_dir)
    if limit_files is not None:
        files = files[:limit_files]

    engine = database.get_connection()
    summary = {
        "data_dir": str(data_dir.resolve()),
        "files_discovered": len(files),
        "files_completed": 0,
        "files_skipped": 0,
        "files_failed": 0,
        "rows_accepted": 0,
        "rows_rejected": 0,
        "errors": [],
    }
    try:
        with engine.begin() as conn:
            database.create_schema(conn)

        for source_file in files:
            registration = None
            try:
                with engine.begin() as conn:
                    registration = register_import(conn, source_file)
                if registration.status == "COMPLETED":
                    summary["files_skipped"] += 1
                    continue

                for chunk in iter_csv_chunks(source_file, chunk_size):
                    chunk = chunk.loc[
                        chunk["source_row_number"] > registration.last_row_number
                    ]
                    if chunk.empty:
                        continue
                    result = transform_air_quality_chunk(chunk)
                    with engine.begin() as conn:
                        load_chunk(
                            conn,
                            registration.id_import_file,
                            result.accepted,
                            result.rejected,
                        )
                    summary["rows_accepted"] += len(result.accepted)
                    summary["rows_rejected"] += len(result.rejected)

                with engine.begin() as conn:
                    complete_import(conn, registration.id_import_file)
                summary["files_completed"] += 1
            except Exception as exc:
                summary["files_failed"] += 1
                summary["errors"].append(f"{source_file.path.name}: {exc}")
                if registration is not None:
                    try:
                        with engine.begin() as conn:
                            fail_import(conn, registration.id_import_file, str(exc))
                    except Exception as status_exc:
                        summary["errors"].append(
                            f"{source_file.path.name}: failed to persist failure status: "
                            f"{status_exc}"
                        )
    finally:
        engine.dispose()
    return summary


def main() -> int:
    args = parse_args()
    if args.chunk_size < 1 or (args.limit_files is not None and args.limit_files < 1):
        raise SystemExit("--chunk-size and --limit-files must be positive")
    try:
        if args.mode == "load":
            summary = load_files(args.data_dir, args.chunk_size, args.limit_files)
        else:
            summary = validate_files(args.data_dir, args.chunk_size, args.limit_files)
    except SourceDataError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    failed = summary.get("files_invalid", 0) + summary.get("files_failed", 0)
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
