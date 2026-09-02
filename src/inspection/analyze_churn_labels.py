"""Compare customer coverage and churn labels in the two KKBox label files."""

from __future__ import annotations

import argparse
import csv
import sys
import tempfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
REPORT_PATH = PROJECT_ROOT / "docs" / "churn_label_analysis.md"
VALID_LABELS = ("0", "1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare customer coverage and labels in train.csv and train_v2.csv."
    )
    parser.add_argument(
        "--progress-every", type=int, default=250_000,
        help="Print progress every this many rows (default: 250,000).",
    )
    args = parser.parse_args()
    if args.progress_every <= 0:
        parser.error("--progress-every must be greater than zero")
    return args


def inspect_labels(path: Path, progress_every: int) -> dict[str, Any]:
    # Retain only one state per customer, never raw CSV rows.
    # State: (first observed label, occurrence count, conflicting labels seen).
    users: dict[str, tuple[str, int, bool]] = {}
    stats = {
        "filename": path.name,
        "total_rows": 0,
        "duplicate_occurrences": 0,
        "duplicated_users": 0,
        "conflicting_users": 0,
        "invalid_labels": 0,
        "missing_labels": 0,
        "churn_rows": 0,
        "non_churn_rows": 0,
    }
    print(f"Scanning {path.name}", flush=True)
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.reader(csv_file, strict=True)
        header = next(reader, None)
        if not header or len(header) != 2 or set(header) != {"msno", "is_churn"}:
            raise ValueError(f"{path.name}: expected msno and is_churn columns")
        user_index = header.index("msno")
        label_index = header.index("is_churn")
        for row in reader:
            stats["total_rows"] += 1
            row_number = stats["total_rows"]
            if len(row) != len(header):
                raise ValueError(f"{path.name}: malformed field count at data row {row_number}")
            msno, label = row[user_index], row[label_index]
            if not msno:
                raise ValueError(f"{path.name}: empty customer key at data row {row_number}")

            # Compare original field strings without trimming or numeric coercion.
            if label == "1":
                stats["churn_rows"] += 1
            elif label == "0":
                stats["non_churn_rows"] += 1
            elif label == "":
                stats["missing_labels"] += 1
            else:
                stats["invalid_labels"] += 1

            previous = users.get(msno)
            if previous is None:
                users[msno] = (label, 1, False)
            else:
                first_label, occurrences, conflicting = previous
                stats["duplicate_occurrences"] += 1
                if occurrences == 1:
                    stats["duplicated_users"] += 1
                if label != first_label and not conflicting:
                    conflicting = True
                    stats["conflicting_users"] += 1
                # Conflicting users remain flagged, not silently assigned one label.
                users[msno] = (first_label, occurrences + 1, conflicting)

            if row_number % progress_every == 0:
                print(f"{path.name}: {row_number:,} rows processed", flush=True)

    stats["distinct_users"] = len(users)
    stats["users"] = users
    print(f"{path.name}: complete ({stats['total_rows']:,} rows)", flush=True)
    return stats


def analyze(progress_every: int) -> dict[str, Any]:
    original = inspect_labels(RAW_DATA_DIR / "train.csv", progress_every)
    v2 = inspect_labels(RAW_DATA_DIR / "train_v2.csv", progress_every)
    original_users = original.pop("users")
    v2_users = v2.pop("users")
    transitions = {(old, new): 0 for old in VALID_LABELS for new in VALID_LABELS}
    shared_users = 0
    excluded_users = 0

    # Iterate existing dictionaries without building extra customer-ID sets.
    for msno, (new_label, _, new_conflicting) in v2_users.items():
        original_state = original_users.get(msno)
        if original_state is None:
            continue
        shared_users += 1
        old_label, _, old_conflicting = original_state
        if (
            old_conflicting or new_conflicting
            or old_label not in VALID_LABELS or new_label not in VALID_LABELS
        ):
            excluded_users += 1
            continue
        transitions[(old_label, new_label)] += 1

    # No customer mappings are returned or included in the report.
    return {
        "original": original,
        "v2": v2,
        "shared_users": shared_users,
        "original_only": original["distinct_users"] - shared_users,
        "v2_only": v2["distinct_users"] - shared_users,
        "excluded_users": excluded_users,
        "transitions": transitions,
    }


def percentage(count: int, total: int) -> str:
    return f"{count / total * 100:.2f}%" if total else "N/A"


def build_report(result: dict[str, Any]) -> str:
    shared = result["shared_users"]
    transitions = result["transitions"]
    same = transitions[("0", "0")] + transitions[("1", "1")]
    changed = transitions[("0", "1")] + transitions[("1", "0")]
    lines = [
        "# Churn Label Analysis", "",
        "## Methodology", "",
        "- Both CSVs were scanned sequentially to completion. Only per-user label "
        "state and counters were retained; no customer identifiers or raw rows are reported.",
        "- Only the exact strings 0 and 1 are valid labels. Empty labels are counted "
        "separately; other non-empty values are invalid. No normalization was applied.",
        "- File churn/non-churn counts are row counts, including repeated customers. "
        "Churn rate is churn rows divided by all valid-label rows; missing and invalid "
        "labels are excluded from this denominator.",
        "- Duplicate occurrences count rows beyond each user's first occurrence. "
        "A conflicting user has differing label strings within one file, including "
        "disagreements involving missing or invalid labels.",
        "- Transitions count each shared user once. Users with conflicting labels "
        "or without a valid label in either file are excluded from transitions, not "
        "silently assigned a label. Identical repeated valid labels remain eligible.",
        "- Transition and label-change percentages use all shared users as the "
        "denominator. When users are excluded, transition percentages need not sum to 100%.",
        "- Observation months are not assigned; competition timing semantics "
        "require separate verification.",
        "", "## File summary", "",
        "| File | Total rows | Distinct users | Churn rows | Non-churn rows | Churn rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for stats in (result["original"], result["v2"]):
        valid_rows = stats["churn_rows"] + stats["non_churn_rows"]
        lines.append(
            f"| {stats['filename']} | {stats['total_rows']:,} | "
            f"{stats['distinct_users']:,} | {stats['churn_rows']:,} | "
            f"{stats['non_churn_rows']:,} | {percentage(stats['churn_rows'], valid_rows)} |"
        )

    lines.extend([
        "", "## User overlap", "",
        "| Metric | Users / percentage |", "| --- | ---: |",
        f"| Users in both files | {shared:,} |",
        f"| Users only in train.csv | {result['original_only']:,} |",
        f"| Users only in train_v2.csv | {result['v2_only']:,} |",
        f"| Percentage of v2 users also in train.csv | "
        f"{percentage(shared, result['v2']['distinct_users'])} |",
        "", "## Label transition matrix", "",
        "| train.csv label | train_v2.csv label | Users | % shared users |",
        "| --- | --- | ---: | ---: |",
    ])
    for (old, new), count in transitions.items():
        lines.append(f"| {old} | {new} | {count:,} | {percentage(count, shared)} |")

    lines.extend([
        "", "## Label stability", "",
        "| Metric | Users | % shared users |", "| --- | ---: | ---: |",
        f"| Label stayed the same | {same:,} | {percentage(same, shared)} |",
        f"| Label changed | {changed:,} | {percentage(changed, shared)} |",
        f"| Excluded: conflicting, invalid, or missing label | "
        f"{result['excluded_users']:,} | {percentage(result['excluded_users'], shared)} |",
        "", "## Duplicate / data-quality checks", "",
        "| File | Duplicate occurrences beyond first | Distinct duplicated users | "
        "Conflicting duplicated users | Invalid non-empty labels | Missing labels |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    for stats in (result["original"], result["v2"]):
        lines.append(
            f"| {stats['filename']} | {stats['duplicate_occurrences']:,} | "
            f"{stats['duplicated_users']:,} | {stats['conflicting_users']:,} | "
            f"{stats['invalid_labels']:,} | {stats['missing_labels']:,} |"
        )

    lines.extend(["", "## Conclusion", ""])
    if changed:
        lines.extend([
            f"{changed:,} shared users have different valid, non-conflicting labels "
            "between the two files.", "",
            "Churn is observed at different time periods and should not be modeled "
            "as a permanent user dimension attribute.",
        ])
    else:
        lines.append(
            "No label changes were observed among shared users with valid, "
            "non-conflicting labels. This does not establish that churn is a "
            "permanent user attribute."
        )
    lines.extend([
        "",
        f"{result['excluded_users']:,} shared users were excluded from label-transition "
        "comparisons because of conflicting, invalid, or missing labels. No observation "
        "months are inferred by this analysis.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    temporary_path: Path | None = None
    try:
        report = build_report(analyze(args.progress_every))
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=REPORT_PATH.parent,
            prefix=".churn_label_analysis_", suffix=".tmp", delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(report)
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
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    print(f"Report written to: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
