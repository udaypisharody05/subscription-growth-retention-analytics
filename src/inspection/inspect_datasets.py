"""Create a lightweight, sample-based inspection report for KKBox CSV files."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
REPORT_PATH = PROJECT_ROOT / "docs" / "dataset_initial_inspection.md"

DATASET_FILENAMES = (
    "members_v3.csv",
    "train.csv",
    "train_v2.csv",
    "transactions.csv",
    "transactions_v2.csv",
    "user_logs.csv",
    "user_logs_v2.csv",
)

DEFAULT_SAMPLE_ROWS = 10_000
MAX_SAMPLE_ROWS = 100_000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect small samples of the raw KKBox CSV files."
    )
    parser.add_argument(
        "--sample-rows",
        type=int,
        default=DEFAULT_SAMPLE_ROWS,
        help=f"Rows to sample per CSV (default: {DEFAULT_SAMPLE_ROWS:,}; "
        f"maximum: {MAX_SAMPLE_ROWS:,}).",
    )
    return parser.parse_args()


def validate_sample_rows(sample_rows: int) -> None:
    if not 1 <= sample_rows <= MAX_SAMPLE_ROWS:
        raise ValueError(
            f"--sample-rows must be between 1 and {MAX_SAMPLE_ROWS:,}."
        )


def inspect_csv(path: Path, sample_rows: int) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Expected dataset not found: {path}")

    # SAFEGUARD: KKBox CSVs can be tens of gigabytes. Every read must remain
    # explicitly bounded by nrows; never load an entire raw CSV into Pandas.
    sample = pd.read_csv(path, nrows=sample_rows, low_memory=False)
    size_bytes = path.stat().st_size

    return {
        "filename": path.name,
        "size_bytes": size_bytes,
        "size_gb": size_bytes / 1_000_000_000,
        "columns": sample.columns.tolist(),
        "column_count": len(sample.columns),
        "dtypes": sample.dtypes.astype(str).to_dict(),
        "has_msno": "msno" in sample.columns,
    }


def build_report(inspections: list[dict[str, Any]], sample_rows: int) -> str:
    lines = [
        "# KKBox Dataset Initial Inspection",
        "",
        (
            f"> This report uses at most {sample_rows:,} rows from each CSV for schema "
            "and dtype inspection. It does not perform any full-file scans."
        ),
        "",
        "## Summary",
        "",
        "| Filename | Size (bytes) | Size (GB) | Columns | Has `msno` |",
        "| --- | ---: | ---: | ---: | :---: |",
    ]

    for item in inspections:
        lines.append(
            f"| {item['filename']} | {item['size_bytes']} | "
            f"{item['size_gb']:.3f} | {item['column_count']} | "
            f"{'Yes' if item['has_msno'] else 'No'} |"
        )

    for item in inspections:
        lines.extend(
            [
                "",
                f"## {item['filename']}",
                "",
                f"- File size: {item['size_bytes']} bytes ({item['size_gb']:.3f} GB)",
                f"- Number of columns: {item['column_count']}",
                f"- Contains `msno`: {'Yes' if item['has_msno'] else 'No'}",
                "",
                "### Columns",
                "",
                ", ".join(f"`{column}`" for column in item["columns"]),
                "",
                "### Sample-inferred dtypes",
                "",
                "| Column | Pandas dtype |",
                "| --- | --- |",
            ]
        )
        lines.extend(
            f"| {column} | {dtype} |" for column, dtype in item["dtypes"].items()
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    validate_sample_rows(args.sample_rows)

    inspections = [
        inspect_csv(RAW_DATA_DIR / filename, args.sample_rows)
        for filename in DATASET_FILENAMES
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        build_report(inspections, args.sample_rows), encoding="utf-8"
    )
    print(f"Inspection report written to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
