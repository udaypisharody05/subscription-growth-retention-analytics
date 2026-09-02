"""Stream raw KKBox CSVs to count rows and profile date coverage."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
REPORT_PATH = PROJECT_ROOT / "docs" / "dataset_full_profile.md"

DATASET_DATE_COLUMNS: dict[str, tuple[str, ...]] = {
    "members_v3.csv": ("registration_init_time",),
    "train.csv": (),
    "train_v2.csv": (),
    "transactions.csv": ("transaction_date", "membership_expire_date"),
    "transactions_v2.csv": ("transaction_date", "membership_expire_date"),
    "user_logs.csv": ("date",),
    "user_logs_v2.csv": ("date",),
}

DEFAULT_PROGRESS_EVERY = 5_000_000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stream KKBox CSVs to calculate exact row counts and date coverage."
    )
    parser.add_argument(
        "--files",
        nargs="+",
        choices=tuple(DATASET_DATE_COLUMNS),
        help="Dataset filenames to profile. If omitted, all datasets are profiled.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=DEFAULT_PROGRESS_EVERY,
        help=f"Print progress after this many rows (default: "
        f"{DEFAULT_PROGRESS_EVERY:,}).",
    )
    args = parser.parse_args()
    if args.progress_every <= 0:
        parser.error("--progress-every must be greater than zero")
    return args


def is_valid_date_value(value: str) -> bool:
    """Return whether a value has the required ASCII YYYYMMDD representation."""
    return len(value) == 8 and value.isascii() and value.isdigit()


def profile_csv(
    path: Path, date_columns: tuple[str, ...], progress_every: int
) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Expected dataset not found: {path}")

    row_count = 0
    malformed_row_count = 0
    next_progress = progress_every
    date_stats = {
        column: {"min": None, "max": None, "invalid_count": 0}
        for column in date_columns
    }

    # MEMORY SAFEGUARD: csv.reader yields one record at a time. Never replace
    # this streaming scan with an unbounded pd.read_csv call or a list of rows.
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.reader(csv_file, strict=True)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError(f"Dataset is empty and has no header: {path}") from exc
        except csv.Error as exc:
            raise ValueError(f"Could not parse header for {path.name}: {exc}") from exc

        expected_column_count = len(header)
        column_indexes = {column: index for index, column in enumerate(header)}
        missing_columns = [
            column for column in date_columns if column not in column_indexes
        ]
        if missing_columns:
            missing = ", ".join(missing_columns)
            raise ValueError(f"{path.name} is missing expected date column(s): {missing}")

        while True:
            try:
                row = next(reader)
            except StopIteration:
                break
            except csv.Error as exc:
                raise ValueError(
                    f"CSV parsing failed in {path.name} near physical line "
                    f"{reader.line_num}: {exc}"
                ) from exc

            row_count += 1

            # A field-count mismatch is detectable without retaining row data.
            # Skip date profiling for that row because its column alignment is unsafe.
            if len(row) != expected_column_count:
                malformed_row_count += 1
            else:
                for column in date_columns:
                    index = column_indexes[column]
                    value = row[index]
                    if not value:
                        continue
                    if not is_valid_date_value(value):
                        date_stats[column]["invalid_count"] += 1
                        continue

                    stats = date_stats[column]
                    if stats["min"] is None or value < stats["min"]:
                        stats["min"] = value
                    if stats["max"] is None or value > stats["max"]:
                        stats["max"] = value

            if row_count >= next_progress:
                print(f"{path.name}: {row_count:,} rows processed", flush=True)
                next_progress += progress_every

    print(f"{path.name}: complete ({row_count:,} rows)", flush=True)
    return {
        "filename": path.name,
        "row_count": row_count,
        "malformed_row_count": malformed_row_count,
        "date_stats": date_stats,
    }


def format_date_summary(profile: dict[str, Any], key: str) -> str:
    date_stats = profile["date_stats"]
    if not date_stats:
        return "N/A"
    return "<br>".join(
        f"{column}: {stats[key] if stats[key] is not None else 'N/A'}"
        for column, stats in date_stats.items()
    )


def build_report(profiles: list[dict[str, Any]]) -> str:
    lines = [
        "# KKBox Dataset Full Profile",
        "",
        (
            "> This report was produced by completed sequential, memory-bounded scans "
            "of the selected raw CSV files. It contains no raw row values or user IDs."
        ),
        "",
        "## Summary",
        "",
        (
            "| Filename | Exact rows | Malformed CSV rows | Minimum date(s) | "
            "Maximum date(s) | Invalid date count(s) |"
        ),
        "| --- | ---: | ---: | --- | --- | --- |",
    ]

    for profile in profiles:
        lines.append(
            f"| {profile['filename']} | {profile['row_count']} | "
            f"{profile['malformed_row_count']} | "
            f"{format_date_summary(profile, 'min')} | "
            f"{format_date_summary(profile, 'max')} | "
            f"{format_date_summary(profile, 'invalid_count')} |"
        )

    for profile in profiles:
        lines.extend(
            [
                "",
                f"## {profile['filename']}",
                "",
                f"- Exact data-row count: {profile['row_count']}",
                f"- Malformed CSV row count: {profile['malformed_row_count']}",
            ]
        )

        if not profile["date_stats"]:
            lines.extend(["", "No date columns are profiled for this dataset."])
            continue

        lines.extend(
            [
                "",
                "| Date column | Minimum valid date | Maximum valid date | "
                "Invalid non-empty values |",
                "| --- | --- | --- | ---: |",
            ]
        )
        for column, stats in profile["date_stats"].items():
            lines.append(
                f"| {column} | {stats['min'] or 'N/A'} | "
                f"{stats['max'] or 'N/A'} | {stats['invalid_count']} |"
            )

    return "\n".join(lines) + "\n"


def write_report_atomically(report: str) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = REPORT_PATH.with_name(f".{REPORT_PATH.name}.tmp")
    try:
        temporary_path.write_text(report, encoding="utf-8")
        temporary_path.replace(REPORT_PATH)
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> int:
    args = parse_args()
    selected_files = list(dict.fromkeys(args.files or DATASET_DATE_COLUMNS))

    try:
        profiles = [
            profile_csv(
                RAW_DATA_DIR / filename,
                DATASET_DATE_COLUMNS[filename],
                args.progress_every,
            )
            for filename in selected_files
        ]
        write_report_atomically(build_report(profiles))
    except KeyboardInterrupt:
        print(
            "\nProfiling interrupted. No report was written for this incomplete run; "
            "any existing report was left unchanged.",
            file=sys.stderr,
        )
        return 130
    except (OSError, ValueError) as exc:
        print(
            f"Profiling failed: {exc}. No report was written for this failed run; "
            "any existing report was left unchanged.",
            file=sys.stderr,
        )
        return 1

    print(f"Profile report written to: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
