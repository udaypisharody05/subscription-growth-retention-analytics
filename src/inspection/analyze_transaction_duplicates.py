"""Compare full transaction rows with SHA-256 and occurrence-aware matching."""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path
from typing import Any, Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
REPORT_PATH = PROJECT_ROOT / "docs" / "transaction_duplicate_analysis.md"
COLUMNS = (
    "msno", "payment_method_id", "payment_plan_days", "plan_list_price",
    "actual_amount_paid", "is_auto_renew", "transaction_date",
    "membership_expire_date", "is_cancel",
)
PERIODS = {
    "historical": "Historical period (transaction_date <= 20170228)",
    "march": "March 2017 (20170301 through 20170331)",
    "other": "Other dates",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare full rows in the two KKBox transaction files."
    )
    parser.add_argument(
        "--progress-every", type=int, default=5_000_000,
        help="Print progress every this many rows (default: 5,000,000).",
    )
    args = parser.parse_args()
    if args.progress_every <= 0:
        parser.error("--progress-every must be greater than zero")
    return args


def read_rows(path: Path) -> Iterator[tuple[str, ...]]:
    # Yield one row at a time. Never collect raw rows or load either CSV in full.
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.reader(csv_file, strict=True)
        header = next(reader, None)
        if not header or len(header) != len(COLUMNS) or set(header) != set(COLUMNS):
            raise ValueError(f"{path.name}: expected exactly the nine transaction columns")
        indexes = [header.index(column) for column in COLUMNS]
        for number, row in enumerate(reader, start=1):
            if len(row) != len(COLUMNS):
                raise ValueError(f"{path.name}: malformed field count at data row {number}")
            yield tuple(row[index] for index in indexes)


def row_hash(row: tuple[str, ...]) -> bytes:
    digest = hashlib.sha256()
    for value in row:
        encoded = value.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, byteorder="big"))
        digest.update(encoded)
    return digest.digest()


def period_for(value: str) -> str:
    if not (len(value) == 8 and value.isascii() and value.isdigit()):
        raise ValueError("Cannot assign a period: transaction_date is not eight ASCII digits")
    if value <= "20170228":
        return "historical"
    if "20170301" <= value <= "20170331":
        return "march"
    return "other"


def analyze(progress_every: int) -> dict[str, Any]:
    # One entry per distinct v2 row: digest -> (remaining occurrences, seen in original).
    # No raw rows are retained. Memory grows with distinct v2 rows, not original rows.
    remaining: dict[bytes, tuple[int, bool]] = {}
    periods = {
        name: {"total": 0, "distinct": 0, "matched": 0, "shared_distinct": 0}
        for name in PERIODS
    }
    v2_total = 0
    duplicate_groups = 0
    v2_path = RAW_DATA_DIR / "transactions_v2.csv"
    print(f"Scanning {v2_path.name}", flush=True)
    for row in read_rows(v2_path):
        v2_total += 1
        stats = periods[period_for(row[6])]
        stats["total"] += 1
        digest = row_hash(row)
        previous = remaining.get(digest)
        if previous is None:
            remaining[digest] = (1, False)
            stats["distinct"] += 1
        else:
            count, _ = previous
            if count == 1:
                duplicate_groups += 1
            remaining[digest] = (count + 1, False)
        if v2_total % progress_every == 0:
            print(f"{v2_path.name}: {v2_total:,} rows processed", flush=True)
    print(f"{v2_path.name}: complete ({v2_total:,} rows)", flush=True)

    original_total = 0
    original_path = RAW_DATA_DIR / "transactions.csv"
    print(f"Scanning {original_path.name}", flush=True)
    for row in read_rows(original_path):
        original_total += 1
        digest = row_hash(row)
        state = remaining.get(digest)
        if state is not None:
            count, seen = state
            if count > 0:
                stats = periods[period_for(row[6])]
                stats["matched"] += 1
                if not seen:
                    stats["shared_distinct"] += 1
                # Consume at most one v2 occurrence per original occurrence.
                remaining[digest] = (count - 1, True)
        if original_total % progress_every == 0:
            print(f"{original_path.name}: {original_total:,} rows processed", flush=True)
    print(f"{original_path.name}: complete ({original_total:,} rows)", flush=True)

    return {
        "original_total": original_total,
        "v2_total": v2_total,
        "v2_distinct": len(remaining),
        "duplicate_groups": duplicate_groups,
        "periods": periods,
    }


def percentage(count: int, total: int) -> str:
    return f"{100 * count / total:.2f}%" if total else "N/A"


def build_report(result: dict[str, Any]) -> str:
    total = result["v2_total"]
    distinct = result["v2_distinct"]
    matched = sum(stats["matched"] for stats in result["periods"].values())
    shared = sum(stats["shared_distinct"] for stats in result["periods"].values())
    lines = [
        "# Transaction Duplicate Analysis", "",
        "## Methodology", "",
        "- Both files were scanned sequentially to completion, with v2 scanned first.",
        "- All nine columns were compared in a fixed order as parsed CSV strings. "
        "No trimming, type coercion, cleaning, or date normalization was applied.",
        "- Each field was encoded as its eight-byte big-endian UTF-8 byte length "
        "followed by its UTF-8 bytes, then the complete record was hashed with SHA-256.",
        "- Hash equality is treated as full-row equality. SHA-256 collision risk is "
        "negligible but not eliminated; raw-row collision verification was not performed.",
        "- Only v2 digests and occurrence/match state were retained. The original file "
        "was streamed without retaining its rows.",
        "- Shared occurrences for a row equal the smaller of its two file counts. "
        "Distinct shared rows are counted once regardless of multiplicity.",
        "- Period percentages use the total v2 occurrences in that period; the overall "
        "percentage uses all v2 occurrences. No identifiers, digests, or records are output.",
        "", "## Overall exact-overlap summary", "",
        "| Metric | Value |", "| --- | ---: |",
        f"| Original file rows scanned | {result['original_total']:,} |",
        f"| Total v2 rows | {total:,} |",
        f"| Distinct v2 full rows | {distinct:,} |",
        f"| Duplicate occurrences within v2 (beyond the first) | {total - distinct:,} |",
        f"| Distinct exact rows shared with original | {shared:,} |",
        f"| Exact v2 occurrences represented in original (multiplicity-aware) | {matched:,} |",
        f"| Exact overlap percentage | {percentage(matched, total)} |",
        f"| V2 occurrences not represented exactly | {total - matched:,} |",
    ]
    for name, label in PERIODS.items():
        stats = result["periods"][name]
        if name == "other" and stats["total"] == 0:
            continue
        lines.extend([
            "", f"## {label}", "",
            "| Metric | Value |", "| --- | ---: |",
            f"| Total v2 rows | {stats['total']:,} |",
            f"| Distinct v2 full rows | {stats['distinct']:,} |",
            f"| Distinct exact rows shared | {stats['shared_distinct']:,} |",
            f"| Exact matched occurrences | {stats['matched']:,} |",
            f"| Exact match percentage | {percentage(stats['matched'], stats['total'])} |",
            f"| Occurrences not exactly matched | {stats['total'] - stats['matched']:,} |",
        ])
    lines.extend([
        "", "## Duplicates within transactions_v2.csv", "",
        f"- Distinct full rows occurring more than once: {result['duplicate_groups']:,}.",
        f"- Duplicate occurrences beyond each row's first occurrence: {total - distinct:,}.",
        "- A row appearing three times contributes two duplicate occurrences.",
        "", "## Conclusion", "",
        f"Under the SHA-256 comparison described above, {shared:,} distinct full rows "
        f"are shared, representing {matched:,} matched occurrences "
        f"({percentage(matched, total)} of v2). {total - matched:,} v2 occurrences "
        "remain unmatched after respecting multiplicity. These counts do not establish "
        "why unmatched records exist or whether they are corrections or new transactions.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    temporary_path = REPORT_PATH.with_name(f".{REPORT_PATH.name}.tmp")
    try:
        result = analyze(args.progress_every)
        report = build_report(result)
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary_path.write_text(report, encoding="utf-8")
        temporary_path.replace(REPORT_PATH)
    except KeyboardInterrupt:
        print("\nAnalysis interrupted; no complete report for this run.", file=sys.stderr)
        return 130
    except (OSError, ValueError, csv.Error, MemoryError) as exc:
        print(
            f"Analysis failed ({type(exc).__name__}): {exc}. "
            "No complete report for this run.", file=sys.stderr,
        )
        return 1
    finally:
        temporary_path.unlink(missing_ok=True)
    print(f"Report written to: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
