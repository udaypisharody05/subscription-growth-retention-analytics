"""Measure hashed customer-key overlap between the two transaction CSVs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path
from typing import Any, Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
REPORT_PATH = PROJECT_ROOT / "docs" / "transaction_key_overlap_analysis.md"
REQUIRED_COLUMNS = ("msno", "transaction_date", "membership_expire_date")
PERIOD_LABELS = {
    "historical": "Historical (transaction_date <= 20170228)",
    "march": "March 2017 (20170301 through 20170331)",
    "other": "Other dates",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure customer-key overlap in the KKBox transaction files."
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


def read_key_fields(path: Path) -> Iterator[tuple[str, str, str]]:
    """Yield msno, transaction_date, and membership_expire_date one row at a time."""
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.reader(csv_file, strict=True)
        header = next(reader, None)
        if not header:
            raise ValueError(f"{path.name}: missing header")
        if any(header.count(column) != 1 for column in REQUIRED_COLUMNS):
            raise ValueError(f"{path.name}: missing or duplicate required key column")
        indexes = [header.index(column) for column in REQUIRED_COLUMNS]

        for row_number, row in enumerate(reader, start=1):
            if len(row) != len(header):
                raise ValueError(
                    f"{path.name}: malformed field count at data row {row_number}"
                )
            yield row[indexes[0]], row[indexes[1]], row[indexes[2]]


def key_hash(namespace: str, *fields: str) -> bytes:
    """Hash a namespaced key using unambiguous length-prefixed UTF-8 fields."""
    digest = hashlib.sha256()
    for field in (namespace, *fields):
        encoded = field.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, byteorder="big"))
        digest.update(encoded)
    return digest.digest()


def period_for(transaction_date: str) -> str:
    if not (
        len(transaction_date) == 8
        and transaction_date.isascii()
        and transaction_date.isdigit()
    ):
        raise ValueError("transaction_date is not eight ASCII digits")
    if transaction_date <= "20170228":
        return "historical"
    if "20170301" <= transaction_date <= "20170331":
        return "march"
    return "other"


def analyze(progress_every: int) -> dict[str, Any]:
    # These sets contain only SHA-256 digests of distinct v2 logical keys.
    v2_users_unmatched: set[bytes] = set()
    v2_transaction_keys_unmatched = {name: set() for name in PERIOD_LABELS}
    v2_expiry_keys_unmatched: set[bytes] = set()

    v2_path = RAW_DATA_DIR / "transactions_v2.csv"
    v2_rows = 0
    print(f"Scanning {v2_path.name}", flush=True)
    for msno, transaction_date, membership_expire_date in read_key_fields(v2_path):
        v2_rows += 1
        period = period_for(transaction_date)
        v2_users_unmatched.add(key_hash("customer", msno))
        v2_transaction_keys_unmatched[period].add(
            key_hash("customer_transaction_date", msno, transaction_date)
        )
        v2_expiry_keys_unmatched.add(
            key_hash("customer_membership_expiry", msno, membership_expire_date)
        )
        if v2_rows % progress_every == 0:
            print(f"{v2_path.name}: {v2_rows:,} rows processed", flush=True)
    print(f"{v2_path.name}: complete ({v2_rows:,} rows)", flush=True)

    initial_v2_users = len(v2_users_unmatched)
    initial_transaction_keys = {
        period: len(keys) for period, keys in v2_transaction_keys_unmatched.items()
    }
    initial_expiry_keys = len(v2_expiry_keys_unmatched)

    # Only distinct hashed users are retained from the original file. Original
    # composite keys and raw rows are never retained; they are tested then discarded.
    original_users: set[bytes] = set()
    original_path = RAW_DATA_DIR / "transactions.csv"
    original_rows = 0
    print(f"Scanning {original_path.name}", flush=True)
    for msno, transaction_date, membership_expire_date in read_key_fields(original_path):
        original_rows += 1
        period = period_for(transaction_date)
        user_key = key_hash("customer", msno)
        original_users.add(user_key)
        v2_users_unmatched.discard(user_key)
        v2_transaction_keys_unmatched[period].discard(
            key_hash("customer_transaction_date", msno, transaction_date)
        )
        v2_expiry_keys_unmatched.discard(
            key_hash("customer_membership_expiry", msno, membership_expire_date)
        )
        if original_rows % progress_every == 0:
            print(f"{original_path.name}: {original_rows:,} rows processed", flush=True)
    print(f"{original_path.name}: complete ({original_rows:,} rows)", flush=True)

    shared_users = initial_v2_users - len(v2_users_unmatched)
    matched_transaction_keys = {
        period: initial_transaction_keys[period] - len(keys)
        for period, keys in v2_transaction_keys_unmatched.items()
    }
    matched_expiry_keys = initial_expiry_keys - len(v2_expiry_keys_unmatched)
    return {
        "original_rows": original_rows,
        "v2_rows": v2_rows,
        "original_users": len(original_users),
        "v2_users": initial_v2_users,
        "shared_users": shared_users,
        "v2_users_only": len(v2_users_unmatched),
        "original_users_only": len(original_users) - shared_users,
        "transaction_keys": initial_transaction_keys,
        "matched_transaction_keys": matched_transaction_keys,
        "expiry_keys": initial_expiry_keys,
        "matched_expiry_keys": matched_expiry_keys,
    }


def percentage(count: int, total: int) -> str:
    return f"{count / total * 100:.2f}%" if total else "N/A"


def build_report(result: dict[str, Any]) -> str:
    transaction_total = sum(result["transaction_keys"].values())
    transaction_matched = sum(result["matched_transaction_keys"].values())
    expiry_total = result["expiry_keys"]
    expiry_matched = result["matched_expiry_keys"]
    historical_total = result["transaction_keys"]["historical"]
    historical_matched = result["matched_transaction_keys"]["historical"]
    lines = [
        "# Transaction Key Overlap Analysis",
        "",
        "## Methodology",
        "",
        "- transactions_v2.csv was scanned first. Distinct customer, "
        "customer+transaction-date, and customer+membership-expiry keys were retained "
        "only as SHA-256 digests.",
        "- Each digest used a key-type namespace and eight-byte length-prefixed UTF-8 "
        "fields, preventing ambiguous field concatenation.",
        "- transactions.csv was then streamed. Matching v2 digests were removed from "
        "the unmatched sets; no original composite-key set or raw row collection was kept.",
        "- A hashed set of distinct original customers was retained solely to calculate "
        "the original distinct-user and original-only-user metrics.",
        "- Metrics count distinct logical keys, not row occurrences. Duplicate "
        "multiplicity is intentionally ignored.",
        "- No hashes, customer identifiers, or raw transaction records are reported. "
        "SHA-256 collision risk is negligible but not eliminated.",
        "",
        "## Customer-level overlap",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| transactions.csv rows scanned | {result['original_rows']:,} |",
        f"| transactions_v2.csv rows scanned | {result['v2_rows']:,} |",
        f"| Distinct users in transactions.csv | {result['original_users']:,} |",
        f"| Distinct users in transactions_v2.csv | {result['v2_users']:,} |",
        f"| Users present in both files | {result['shared_users']:,} |",
        f"| Users only in transactions.csv | {result['original_users_only']:,} |",
        f"| Users only in transactions_v2.csv | {result['v2_users_only']:,} |",
        f"| Percentage of v2 users seen in original | "
        f"{percentage(result['shared_users'], result['v2_users'])} |",
        "",
        "## Customer + transaction-date overlap",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Distinct v2 keys | {transaction_total:,} |",
        f"| V2 keys found in transactions.csv | {transaction_matched:,} |",
        f"| Overlap percentage | {percentage(transaction_matched, transaction_total)} |",
        f"| Historical distinct v2 keys | {historical_total:,} |",
        f"| Historical v2 keys found in original | {historical_matched:,} |",
        f"| Historical v2 keys not found in original | "
        f"{historical_total - historical_matched:,} |",
        f"| March v2 keys found in original | "
        f"{result['matched_transaction_keys']['march']:,} |",
        "",
        "## Customer + membership-expiry overlap",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Distinct v2 keys | {expiry_total:,} |",
        f"| V2 keys found in transactions.csv | {expiry_matched:,} |",
        f"| Overlap percentage | {percentage(expiry_matched, expiry_total)} |",
        f"| V2 keys not found in transactions.csv | {expiry_total - expiry_matched:,} |",
        "",
        "## Historical vs March comparison",
        "",
        "| V2 transaction-date-key period | Distinct keys | Found in original | "
        "Not found in original | Overlap percentage |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for period in ("historical", "march", "other"):
        total = result["transaction_keys"][period]
        if period == "other" and total == 0:
            continue
        matched = result["matched_transaction_keys"][period]
        lines.append(
            f"| {PERIOD_LABELS[period]} | {total:,} | {matched:,} | "
            f"{total - matched:,} | {percentage(matched, total)} |"
        )

    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            f"- {result['shared_users']:,} of {result['v2_users']:,} distinct v2 "
            f"customers ({percentage(result['shared_users'], result['v2_users'])}) "
            "were also observed in transactions.csv.",
            f"- {historical_matched:,} of {historical_total:,} distinct historical v2 "
            "customer+transaction-date keys "
            f"({percentage(historical_matched, historical_total)}) were found in "
            "transactions.csv.",
            "- These key-level relationships do not prove that records are duplicates, "
            "corrections, replacements, or updates.",
        ]
    )
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
        print("\nAnalysis interrupted; no complete report was written.", file=sys.stderr)
        return 130
    except (OSError, ValueError, csv.Error, MemoryError) as exc:
        print(
            f"Analysis failed ({type(exc).__name__}): {exc}. "
            "No complete report was written.",
            file=sys.stderr,
        )
        return 1
    finally:
        temporary_path.unlink(missing_ok=True)

    print(f"Report written to: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
