"""Compare transaction-date counts using sequential, memory-safe CSV scans."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
REPORT_PATH = PROJECT_ROOT / "docs" / "transaction_overlap_analysis.md"
FILENAMES = ("transactions.csv", "transactions_v2.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare date coverage in the two KKBox transaction files."
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=5_000_000,
        help="Print progress every this many rows (default: 5,000,000).",
    )
    args = parser.parse_args()
    if args.progress_every <= 0:
        parser.error("--progress-every must be greater than zero")
    return args


def count_dates(path: Path, progress_every: int) -> dict[str, Any]:
    total_rows = 0
    date_counts: Counter[str] = Counter()
    month_counts: Counter[str] = Counter()
    print(f"Scanning {path.name}", flush=True)

    # Keep only date/month counters, never a collection of rows or customer IDs.
    # csv.reader streams one record at a time; do not replace it with a full load.
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.reader(csv_file, strict=True)
        header = next(reader, None)
        if not header or header.count("transaction_date") != 1:
            raise ValueError(f"{path.name}: expected one transaction_date column")
        date_index = header.index("transaction_date")

        for row in reader:
            total_rows += 1
            if len(row) != len(header):
                raise ValueError(
                    f"{path.name}: malformed field count at data row {total_rows}"
                )

            value = row[date_index]
            if value not in date_counts:
                # Validate each distinct date once, not once per transaction.
                if not (len(value) == 8 and value.isascii() and value.isdigit()):
                    raise ValueError(
                        f"{path.name}: invalid date at data row {total_rows}"
                    )
                try:
                    date(int(value[:4]), int(value[4:6]), int(value[6:8]))
                except ValueError as exc:
                    raise ValueError(
                        f"{path.name}: invalid date at data row {total_rows}"
                    ) from exc

            date_counts[value] += 1
            month_counts[f"{value[:4]}-{value[4:6]}"] += 1
            if total_rows % progress_every == 0:
                print(f"{path.name}: {total_rows:,} rows processed", flush=True)

    print(f"{path.name}: complete ({total_rows:,} rows)", flush=True)
    return {
        "filename": path.name,
        "total_rows": total_rows,
        "date_counts": date_counts,
        "month_counts": month_counts,
    }


def percentage(count: int, total: int) -> str:
    return f"{count / total * 100:.2f}%" if total else "N/A"


def build_report(original: dict[str, Any], v2: dict[str, Any]) -> str:
    original_dates = original["date_counts"]
    v2_dates = v2["date_counts"]
    shared_dates = sorted(original_dates.keys() & v2_dates.keys())
    original_only = sorted(original_dates.keys() - v2_dates.keys())
    v2_only = sorted(v2_dates.keys() - original_dates.keys())
    historical_rows = sum(
        count for value, count in v2_dates.items() if value <= "20170228"
    )
    march_rows = sum(
        count for value, count in v2_dates.items()
        if "20170301" <= value <= "20170331"
    )
    other_rows = v2["total_rows"] - historical_rows - march_rows

    lines = [
        "# Transaction Overlap Analysis",
        "",
        "> Completed sequential, memory-safe scans. Only aggregate date/month counts "
        "are reported; no customer identifiers or raw transaction records are included.",
        "",
        "## File summary",
        "",
        "| Filename | Total data rows | Distinct transaction dates |",
        "| --- | ---: | ---: |",
    ]
    for result in (original, v2):
        lines.append(
            f"| {result['filename']} | {result['total_rows']:,} | "
            f"{len(result['date_counts']):,} |"
        )

    lines.extend([
        "",
        "## transactions_v2.csv period breakdown",
        "",
        "Percentages use all data rows in transactions_v2.csv as the denominator. "
        "The historical overlap period here means dates on or before 20170228; "
        "it does not imply that individual records match the original file.",
        "",
        "| Period | Rows | Percentage of v2 rows |",
        "| --- | ---: | ---: |",
    ])
    for label, count in (
        ("Historical overlap period (<= 20170228)", historical_rows),
        ("March 2017 (20170301 to 20170331)", march_rows),
        ("Other dates", other_rows),
    ):
        lines.append(
            f"| {label} | {count:,} | {percentage(count, v2['total_rows'])} |"
        )

    lines.extend(["", "## Date-set comparison", ""])
    lines.append(f"Number of overlapping dates: {len(shared_dates):,}.")
    for label, values in (
        ("Dates present in both files", shared_dates),
        ("Dates only in transactions.csv", original_only),
        ("Dates only in transactions_v2.csv", v2_only),
    ):
        lines.extend(["", f"### {label}", "", ", ".join(values) or "N/A"])

    for result in (original, v2):
        lines.extend([
            "", f"## Monthly counts: {result['filename']}", "",
            "| Month | Rows |", "| --- | ---: |",
        ])
        for month, count in sorted(result["month_counts"].items()):
            lines.append(f"| {month} | {count:,} |")

    shared_months = sorted(
        original["month_counts"].keys() & v2["month_counts"].keys()
    )
    lines.extend([
        "", "## Overlapping-month comparison", "",
        "Difference = transactions_v2.csv rows minus transactions.csv rows.", "",
        "| Month | transactions.csv rows | transactions_v2.csv rows | Difference |",
        "| --- | ---: | ---: | ---: |",
    ])
    for month in shared_months:
        original_count = original["month_counts"][month]
        v2_count = v2["month_counts"][month]
        lines.append(
            f"| {month} | {original_count:,} | {v2_count:,} | "
            f"{v2_count - original_count:,} |"
        )
    if not shared_months:
        lines.extend(["", "No overlapping months."])

    lines.extend([
        "", "## Daily counts", "",
        "Zero means the date was absent from that file.", "",
        "| Transaction date | transactions.csv rows | transactions_v2.csv rows |",
        "| --- | ---: | ---: |",
    ])
    for value in sorted(original_dates.keys() | v2_dates.keys()):
        lines.append(
            f"| {value} | {original_dates[value]:,} | {v2_dates[value]:,} |"
        )

    lines.extend([
        "", "## Conclusions (date-level counts only)", "",
        f"- transactions_v2.csv contains {historical_rows:,} historical-dated rows "
        f"(<= 20170228) and {march_rows:,} rows dated in March 2017.",
        f"- {len(shared_dates):,} transaction dates are present in both files.",
        "- Shared dates do not establish duplicate transactions. Exact row duplication "
        "and customer/date duplication have not been tested.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    temporary_path = REPORT_PATH.with_name(f".{REPORT_PATH.name}.tmp")
    try:
        original = count_dates(RAW_DATA_DIR / FILENAMES[0], args.progress_every)
        v2 = count_dates(RAW_DATA_DIR / FILENAMES[1], args.progress_every)
        report = build_report(original, v2)
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary_path.write_text(report, encoding="utf-8")
        temporary_path.replace(REPORT_PATH)
    except KeyboardInterrupt:
        print("\nAnalysis interrupted; no completed report for this run.", file=sys.stderr)
        return 130
    except (OSError, ValueError, csv.Error) as exc:
        print(f"Analysis failed: {exc}. No completed report for this run.", file=sys.stderr)
        return 1
    finally:
        temporary_path.unlink(missing_ok=True)

    print(f"Report written to: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
