"""Stream KKBox files and accumulate aggregate member-coverage results."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
REFERENCE_PATH = RAW_DATA_DIR / "members_v3.csv"
CACHE_PATH = (
    PROJECT_ROOT / "data" / "processed" / "inspection" / "member_coverage_results.json"
)
REPORT_PATH = PROJECT_ROOT / "docs" / "member_coverage_analysis.md"
SOURCE_FILES = (
    "transactions.csv", "transactions_v2.csv", "train.csv", "train_v2.csv",
    "user_logs.csv", "user_logs_v2.csv",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze KKBox member coverage safely.")
    parser.add_argument(
        "--files", nargs="+", choices=SOURCE_FILES,
        help="Source files to scan; default: all six. The member reference is always read.",
    )
    parser.add_argument(
        "--progress-every", type=int, default=5_000_000,
        help="Print progress every this many rows (default: 5,000,000).",
    )
    args = parser.parse_args()
    if args.progress_every <= 0:
        parser.error("--progress-every must be greater than zero")
    return args


def file_identity(path: Path) -> dict[str, int]:
    stat = path.stat()
    return {"size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def read_identifiers(path: Path) -> Iterator[str]:
    # Stream one CSV record at a time; never retain a raw row collection.
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.reader(csv_file, strict=True)
        header = next(reader, None)
        if not header or header.count("msno") != 1:
            raise ValueError(f"{path.name}: expected exactly one msno column")
        index = header.index("msno")
        for number, row in enumerate(reader, start=1):
            if len(row) != len(header):
                raise ValueError(f"{path.name}: malformed field count at data row {number}")
            yield row[index]


def scan_members(progress_every: int) -> tuple[dict[str, bool], dict[str, Any]]:
    identity = file_identity(REFERENCE_PATH)
    # Anonymized identifier -> whether this member was counted as a duplicated user.
    # Identifiers stay in local memory only; never persist, print, or report them.
    members: dict[str, bool] = {}
    stats = {
        "total_rows": 0, "duplicate_occurrences": 0,
        "duplicated_users": 0, "empty_identifiers": 0,
    }
    print(f"Scanning {REFERENCE_PATH.name}", flush=True)
    for identifier in read_identifiers(REFERENCE_PATH):
        stats["total_rows"] += 1
        if identifier == "":
            stats["empty_identifiers"] += 1
        else:
            duplicated = members.get(identifier)
            if duplicated is None:
                members[identifier] = False
            else:
                stats["duplicate_occurrences"] += 1
                if not duplicated:
                    members[identifier] = True
                    stats["duplicated_users"] += 1
        if stats["total_rows"] % progress_every == 0:
            print(
                f"{REFERENCE_PATH.name}: {stats['total_rows']:,} rows processed",
                flush=True,
            )
    if file_identity(REFERENCE_PATH) != identity:
        raise ValueError("Member reference changed during its scan")
    stats.update(
        distinct_users=len(members), file_identity=identity, status="complete",
        completed_at=datetime.now(timezone.utc).isoformat(),
    )
    print(f"{REFERENCE_PATH.name}: complete ({stats['total_rows']:,} rows)", flush=True)
    return members, stats


def scan_source(
    path: Path, members: dict[str, bool], progress_every: int
) -> dict[str, Any]:
    identity = file_identity(path)
    seen: set[str] = set()
    stats = {
        "total_rows": 0, "empty_identifiers": 0,
        "users_with_member": 0, "rows_with_member": 0,
    }
    print(f"Scanning {path.name}", flush=True)
    for identifier in read_identifiers(path):
        stats["total_rows"] += 1
        if identifier == "":
            stats["empty_identifiers"] += 1
        else:
            has_member = identifier in members
            if has_member:
                stats["rows_with_member"] += 1
            if identifier not in seen:
                seen.add(identifier)
                if has_member:
                    stats["users_with_member"] += 1
        if stats["total_rows"] % progress_every == 0:
            print(f"{path.name}: {stats['total_rows']:,} rows processed", flush=True)
    if file_identity(path) != identity:
        raise ValueError(f"{path.name}: file changed during its scan")
    stats.update(
        distinct_users=len(seen),
        users_without_member=len(seen) - stats["users_with_member"],
        rows_without_member=stats["total_rows"] - stats["rows_with_member"],
        file_identity=identity, status="complete",
        completed_at=datetime.now(timezone.utc).isoformat(),
    )
    print(f"{path.name}: complete ({stats['total_rows']:,} rows)", flush=True)
    # Return aggregates only. This source's identifier set is released on return.
    return stats


def load_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {"version": 1, "reference": None, "sources": {}}
    with CACHE_PATH.open("r", encoding="utf-8") as cache_file:
        cache = json.load(cache_file)
    if (
        not isinstance(cache, dict) or cache.get("version") != 1
        or not isinstance(cache.get("sources"), dict)
        or not isinstance(cache.get("reference"), dict)
    ):
        raise ValueError("Unsupported or malformed cache; it has not been overwritten")
    for name, result in cache["sources"].items():
        if (
            name not in SOURCE_FILES or not isinstance(result, dict)
            or result.get("status") != "complete"
        ):
            raise ValueError("Cache contains an invalid source result")
    return cache


def percentage(count: int, total: int) -> str:
    if not total:
        return "N/A"
    formatted = f"{count / total * 100:.4f}"
    # Even a tiny unmatched fraction must not be presented as complete coverage.
    if count < total and formatted == "100.0000":
        return "<100.0000%"
    return f"{formatted}%"


def build_report(cache: dict[str, Any]) -> str:
    reference = cache["reference"]
    sources = cache["sources"]
    lines = [
        "# KKBox Member Coverage Analysis", "",
        "## Methodology", "",
        "- The member reference and each source are scanned sequentially. Anonymized "
        "msno values are retained only transiently in local memory, with one source "
        "set at a time; identifiers are never persisted, printed, or reported.",
        "- Identifier strings are compared directly, without trimming or normalization.",
        "- Empty identifiers are excluded from distinct-user and duplicate-user counts. "
        "Empty source rows are counted as rows without member metadata.",
        "- User coverage uses distinct non-empty source users as the denominator. "
        "Row coverage uses all source data rows, including empty identifiers.",
        "- Only completed aggregate results are cached. Selected runs preserve "
        "unrelated cached results, and interrupted scans do not replace prior results.",
        "- Results describe file snapshots at their recorded completion times. "
        "File sizes and modification times guard against changed inputs; they are not "
        "content checksums. No identifiers, hashes, or sample records are published.",
        "", "## members_v3 Integrity", "",
        "| Metric | Value |", "| --- | ---: |",
        f"| Total rows | {reference['total_rows']:,} |",
        f"| Distinct non-empty users | {reference['distinct_users']:,} |",
        f"| Duplicate occurrences beyond first | {reference['duplicate_occurrences']:,} |",
        f"| Distinct duplicated users | {reference['duplicated_users']:,} |",
        f"| Empty identifiers | {reference['empty_identifiers']:,} |",
        "", f"Reference scan completed: {reference['completed_at']}",
        "", "## Coverage Summary", "",
        "| Source | Rows | Distinct users | Users with member record | "
        "Users without member record | User coverage % | Row coverage % |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in SOURCE_FILES:
        if name not in sources:
            continue
        result = sources[name]
        lines.append(
            f"| {name} | {result['total_rows']:,} | {result['distinct_users']:,} | "
            f"{result['users_with_member']:,} | {result['users_without_member']:,} | "
            f"{percentage(result['users_with_member'], result['distinct_users'])} | "
            f"{percentage(result['rows_with_member'], result['total_rows'])} |"
        )
    pending = [name for name in SOURCE_FILES if name not in sources]
    if pending:
        lines.extend(["", "No completed cached result for: " + ", ".join(pending) + "."])

    lines.extend(["", "## Dataset Details"])
    for name in SOURCE_FILES:
        if name not in sources:
            continue
        result = sources[name]
        unmatched_rows_label = "Rows without member metadata"
        if result["empty_identifiers"] > 0:
            unmatched_rows_label += " (including empty identifiers)"
        lines.extend([
            "", f"### {name}", "",
            f"Completed: {result['completed_at']}", "",
            "| Metric | Value |", "| --- | ---: |",
            f"| Total rows scanned | {result['total_rows']:,} |",
            f"| Distinct non-empty users | {result['distinct_users']:,} |",
            f"| Users with member metadata | {result['users_with_member']:,} |",
            f"| Users without member metadata | {result['users_without_member']:,} |",
            f"| User coverage | "
            f"{percentage(result['users_with_member'], result['distinct_users'])} |",
            f"| Rows with member metadata | {result['rows_with_member']:,} |",
            f"| {unmatched_rows_label} | "
            f"{result['rows_without_member']:,} |",
            f"| Row coverage | {percentage(result['rows_with_member'], result['total_rows'])} |",
            f"| Empty identifier rows | {result['empty_identifiers']:,} |",
        ])

    lines.extend(["", "## Modeling Implications", ""])
    for name in SOURCE_FILES:
        if name not in sources:
            continue
        result = sources[name]
        if result["total_rows"] == 0:
            lines.append(f"- {name}: no source data rows; coverage is undefined.")
        elif result["rows_without_member"]:
            empty_note = (
                f", including {result['empty_identifiers']:,} empty-identifier rows"
                if result["empty_identifiers"] > 0 else ""
            )
            lines.append(
                f"- {name}: member coverage is incomplete. An inner join to members_v3 "
                f"would remove {result['users_without_member']:,} distinct non-empty "
                f"source users and {result['rows_without_member']:,} source rows "
                f"without matching metadata{empty_note}."
            )
        else:
            lines.append(
                f"- {name}: all scanned source users and rows have member metadata; "
                "none would be removed solely for a missing member match."
            )
    lines.extend([
        "",
        "members_v3 does not provide complete customer coverage across the transaction, "
        "churn-label, and activity sources; using it as the mandatory side of an inner "
        "join would exclude valid source records.",
        "",
        "No final modeling decision is made and no SQL tables are created.",
    ])
    return "\n".join(lines) + "\n"


def atomic_write(path: Path, content: str) -> None:
    temporary_path: Path | None = None
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}_", suffix=".tmp", delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def save_results(cache: dict[str, Any]) -> None:
    # Render before writing; replace the cache before publishing its report.
    report = build_report(cache)
    atomic_write(CACHE_PATH, json.dumps(cache, indent=2, ensure_ascii=True) + "\n")
    atomic_write(REPORT_PATH, report)


def main() -> int:
    args = parse_args()
    selected_files = list(dict.fromkeys(args.files or SOURCE_FILES))
    lock_path = CACHE_PATH.with_suffix(".lock")
    lock_acquired = False
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            with lock_path.open("x", encoding="utf-8"):
                lock_acquired = True
        except FileExistsError as exc:
            raise ValueError(
                f"Another run or a stale lock exists at {lock_path}. "
                "Do not remove the lock while a scan is active."
            ) from exc
        cache = load_cache()
        identity = file_identity(REFERENCE_PATH)
        if cache["sources"] and cache["reference"]["file_identity"] != identity:
            raise ValueError(
                "Member reference differs from the cached reference. Preserve/archive "
                "the old cache before starting a new reference version."
            )
        members, reference = scan_members(args.progress_every)
        if reference["file_identity"] != identity:
            raise ValueError("Member reference changed before scanning began")
        cache = {**cache, "reference": reference}
        save_results(cache)
        for name in selected_files:
            result = scan_source(RAW_DATA_DIR / name, members, args.progress_every)
            if file_identity(REFERENCE_PATH) != identity:
                raise ValueError("Member reference changed during source scanning")
            updated = {**cache, "sources": {**cache["sources"], name: result}}
            save_results(updated)
            cache = updated
            print(f"Saved completed result: {name}", flush=True)
    except KeyboardInterrupt:
        print("\nCoverage analysis interrupted. Incomplete scans are not saved.", file=sys.stderr)
        return 130
    except (OSError, ValueError, csv.Error, MemoryError, KeyError, TypeError) as exc:
        print(f"Coverage analysis failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        print(
            "Incomplete scans are not saved. Completed cache entries remain available; "
            "the Markdown report may reflect an earlier completed snapshot.", file=sys.stderr,
        )
        return 1
    finally:
        if lock_acquired:
            lock_path.unlink(missing_ok=True)
    print(f"Report written to: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
