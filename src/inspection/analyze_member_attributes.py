"""Stream members_v3.csv to profile attribute quality without cleaning values."""

from __future__ import annotations

import argparse
import csv
import html
import sys
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = PROJECT_ROOT / "data" / "raw" / "members_v3.csv"
REPORT_PATH = PROJECT_ROOT / "docs" / "member_attribute_analysis.md"
EXPECTED_COLUMNS = (
    "msno", "city", "bd", "gender", "registered_via", "registration_init_time",
)
ATTRIBUTES = EXPECTED_COLUMNS[1:]
QUANTILES = (
    ("p01", 1), ("p05", 5), ("p25", 25), ("median", 50),
    ("p75", 75), ("p95", 95), ("p99", 99),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile KKBox member attributes.")
    parser.add_argument(
        "--progress-every", type=int, default=500_000,
        help="Print progress every this many rows (default: 500,000).",
    )
    args = parser.parse_args()
    if args.progress_every <= 0:
        parser.error("--progress-every must be greater than zero")
    return args


def scan_attributes(progress_every: int) -> dict[str, Any]:
    frequencies: dict[str, Counter[str]] = {name: Counter() for name in ATTRIBUTES}
    empty: Counter[str] = Counter()
    total_rows = 0
    print(f"Scanning {SOURCE_PATH.name}", flush=True)
    # Retain only attribute frequencies, never customer identifiers or raw rows.
    with SOURCE_PATH.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.reader(csv_file, strict=True)
        header = next(reader, None)
        if header is None or tuple(header) != EXPECTED_COLUMNS:
            raise ValueError("members_v3.csv: header must match the exact expected columns/order")
        for row in reader:
            total_rows += 1
            if len(row) != len(EXPECTED_COLUMNS):
                raise ValueError(f"members_v3.csv: malformed field count at data row {total_rows}")
            for index, name in enumerate(ATTRIBUTES, start=1):
                value = row[index]
                if value == "":
                    empty[name] += 1
                else:
                    frequencies[name][value] += 1
            if total_rows % progress_every == 0:
                print(f"members_v3.csv: {total_rows:,} rows processed", flush=True)
    print(f"members_v3.csv: complete ({total_rows:,} rows)", flush=True)
    return {"total_rows": total_rows, "empty": empty, "frequencies": frequencies}


def integer_value(value: str) -> int | None:
    digits = value[1:] if value.startswith(("+", "-")) else value
    if not digits or not digits.isascii() or not digits.isdigit():
        return None
    return int(value)


def numeric_summary(frequencies: Counter[str]) -> dict[str, Any]:
    numeric: Counter[int] = Counter()
    non_integer_rows = 0
    for value, count in frequencies.items():
        parsed = integer_value(value)
        if parsed is None:
            non_integer_rows += count
        else:
            numeric[parsed] += count
    return {
        "frequencies": numeric,
        "non_integer_rows": non_integer_rows,
        "numeric_rows": sum(numeric.values()),
        "min": min(numeric) if numeric else None,
        "max": max(numeric) if numeric else None,
    }


def numeric_quantiles(frequencies: Counter[int]) -> dict[str, str]:
    """Exact linear-interpolated quantiles from weighted order statistics."""
    total = sum(frequencies.values())
    if not total:
        return {label: "N/A" for label, _ in QUANTILES}
    ordered = sorted(frequencies.items())

    def value_at(index: int) -> int:
        cumulative = 0
        for value, count in ordered:
            cumulative += count
            if index < cumulative:
                return value
        raise ValueError("Quantile rank exceeds the numeric population")

    results = {}
    for label, percentile in QUANTILES:
        lower, remainder = divmod((total - 1) * percentile, 100)
        low_value = value_at(lower)
        high_value = value_at(lower + 1) if remainder else low_value
        # Integer arithmetic preserves exact hundredths without float rounding.
        hundredths = low_value * (100 - remainder) + high_value * remainder
        whole, fraction = divmod(abs(hundredths), 100)
        sign = "-" if hundredths < 0 else ""
        text = f"{sign}{whole}"
        if fraction:
            text += "." + f"{fraction:02d}".rstrip("0")
        results[label] = text
    return results


def registration_summary(frequencies: Counter[str]) -> dict[str, Any]:
    years: Counter[int] = Counter()
    earliest = latest = None
    invalid = before = after = 0
    for value, count in frequencies.items():
        if not (len(value) == 8 and value.isascii() and value.isdigit()):
            invalid += count
            continue
        try:
            parsed = date(int(value[:4]), int(value[4:6]), int(value[6:8]))
        except ValueError:
            invalid += count
            continue
        years[parsed.year] += count
        if earliest is None or parsed < earliest:
            earliest = parsed
        if latest is None or parsed > latest:
            latest = parsed
        if parsed < date(2004, 1, 1):
            before += count
        if parsed > date(2017, 12, 31):
            after += count
    return {
        "invalid": invalid, "min": earliest, "max": latest,
        "before": before, "after": after, "years": years,
    }


def percentage(count: int, total: int) -> str:
    return f"{count / total * 100:.4f}%" if total else "N/A"


def display(value: Any) -> str:
    return str(value) if value is not None else "N/A"


def frequency_table(
    frequencies: Counter[str], total: int, empty: int, limit: int | None
) -> list[str]:
    lines = [
        "| Source value | Rows | % of all rows |", "| --- | ---: | ---: |",
        f"| (empty field) | {empty:,} | {percentage(empty, total)} |",
    ]
    for value, count in frequencies.most_common(limit):
        escaped = html.escape(value, quote=False).replace("|", "&#124;")
        escaped = escaped.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
        lines.append(f"| <code>{escaped}</code> | {count:,} | {percentage(count, total)} |")
    if limit is not None and len(frequencies) > limit:
        lines.extend([
            "", f"Top {limit} of {len(frequencies):,} distinct non-empty values shown. "
            "Frequencies for all values were calculated.",
        ])
    return lines


def build_report(profile: dict[str, Any]) -> str:
    total = profile["total_rows"]
    empty = profile["empty"]
    frequencies = profile["frequencies"]
    numeric = {
        name: numeric_summary(frequencies[name])
        for name in ("city", "bd", "registered_via")
    }
    registration = registration_summary(frequencies["registration_init_time"])
    lines = [
        "# KKBox Member Attribute Analysis", "",
        "## Methodology", "",
        f"- Completed a sequential scan of {total:,} data rows, excluding the header.",
        "- The exact six-column schema and record field counts were validated. Only "
        "attribute frequency distributions were retained; no customer identifiers are reported.",
        "- Empty means an exactly empty CSV field. No trimming, normalization, "
        "replacement, deletion, capping, or other cleaning was performed.",
        "- Distinct non-empty values use original field strings. Integer validation "
        "accepts an optional single sign followed by ASCII digits. Numeric summaries "
        "combine equivalent integer representations for statistical calculation only.",
        "- bd quantiles exclude empty/non-integer values and use exact linear "
        "interpolation at zero-based position (N - 1) * p, weighted by frequencies. "
        "The median averages the two central values when N is even.",
        "- Registration dates must have eight ASCII digits and be valid calendar "
        "dates. Each distinct value is parsed once, with row counts weighted by frequency.",
        "- Percentages use all scanned rows as their denominator. Numeric/date "
        "ranges use only successfully parsed values. N/A indicates no applicable range.",
        "- Thresholds for bd and registration dates are inspection checks, not "
        "decisions that the values are invalid.",
        "", "## Completeness Summary", "",
        "| Attribute | Empty rows | Empty % | Distinct non-empty values |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name in ATTRIBUTES:
        lines.append(
            f"| {name} | {empty[name]:,} | {percentage(empty[name], total)} | "
            f"{len(frequencies[name]):,} |"
        )

    for name, heading in (("city", "City"), ("bd", "bd"), ("gender", "Gender"),
                          ("registered_via", "registered_via")):
        lines.extend([
            "", f"## {heading}", "",
            f"- Total rows: {total:,}.",
            f"- Empty values: {empty[name]:,}.",
            f"- Distinct non-empty values: {len(frequencies[name]):,}.",
        ])
        if name in numeric:
            summary = numeric[name]
            applicable = name == "bd" or summary["non_integer_rows"] == 0
            lines.extend([
                f"- Non-integer non-empty rows: {summary['non_integer_rows']:,}.",
                f"- Minimum numeric value: {display(summary['min'] if applicable else None)}.",
                f"- Maximum numeric value: {display(summary['max'] if applicable else None)}.",
            ])
            if not applicable:
                lines.append("- Code range is N/A because not all non-empty values are integers.")
        if name == "bd":
            counts = numeric[name]["frequencies"]
            lines.extend([
                f"- Numeric rows: {numeric[name]['numeric_rows']:,}.",
                f"- Distinct numeric values: {len(counts):,}.", "",
                "| Numeric check | Rows |", "| --- | ---: |",
                f"| bd < 0 | {sum(n for value, n in counts.items() if value < 0):,} |",
                f"| bd = 0 | {counts[0]:,} |",
                f"| bd > 0 | {sum(n for value, n in counts.items() if value > 0):,} |",
                f"| bd > 100 | {sum(n for value, n in counts.items() if value > 100):,} |",
                f"| bd > 120 | {sum(n for value, n in counts.items() if value > 120):,} |",
                "", "The positive thresholds overlap; they are not disjoint categories.",
                "", "| Quantile | Numeric value |", "| --- | ---: |",
            ])
            lines.extend(f"| {label} | {value} |" for label, value in numeric_quantiles(counts).items())
        lines.append("")
        limit = None if name in ("gender", "registered_via") else (20 if name == "bd" else 100)
        lines.extend(frequency_table(frequencies[name], total, empty[name], limit))
        if name in ("city", "registered_via"):
            lines.extend(["", "No real-world meanings are assigned to these source codes."])

    lines.extend([
        "", "## Registration Date", "",
        "| Metric | Value |", "| --- | ---: |",
        f"| Empty values | {empty['registration_init_time']:,} |",
        f"| Invalid non-empty values | {registration['invalid']:,} |",
        f"| Minimum valid date | {display(registration['min'])} |",
        f"| Maximum valid date | {display(registration['max'])} |",
        f"| Valid-date rows before 2004-01-01 | {registration['before']:,} |",
        f"| Valid-date rows after 2017-12-31 | {registration['after']:,} |",
        f"| Distinct valid registration years | {len(registration['years']):,} |",
        "", "| Registration year | Rows |", "| --- | ---: |",
    ])
    lines.extend(f"| {year} | {count:,} |" for year, count in sorted(registration["years"].items()))

    bd_counts = numeric["bd"]["frequencies"]
    negative = sum(count for value, count in bd_counts.items() if value < 0)
    above_100 = sum(count for value, count in bd_counts.items() if value > 100)
    above_120 = sum(count for value, count in bd_counts.items() if value > 120)
    lines.extend(["", "## Data Quality Findings", ""])
    for name in ATTRIBUTES:
        lines.append(f"- {name}: {empty[name]:,} empty rows.")
    lines.extend([
        f"- bd has {negative:,} negative, {bd_counts[0]:,} zero, {above_100:,} above-100, "
        f"and {above_120:,} above-120 numeric rows. These counts do not establish a cleaning rule.",
        f"- Registration dates have {registration['invalid']:,} invalid non-empty rows, "
        f"{registration['before']:,} valid rows before 2004-01-01, and "
        f"{registration['after']:,} valid rows after 2017-12-31.",
        "", "## Implications for dim_user", "",
    ])
    for name in ("city", "registered_via"):
        if numeric[name]["numeric_rows"] and not numeric[name]["non_integer_rows"]:
            lines.append(
                f"- {name}: all non-empty values are integer-like source codes. "
                "Code meanings and final representation are not assigned here."
            )
        else:
            lines.append(
                f"- {name}: {numeric[name]['non_integer_rows']:,} non-integer rows; "
                "do not assume an integer-only representation without resolving source validity."
            )
    lines.extend([
        "- Fields with reported empty values need an explicit missing-value policy. "
        "Gender values remain as observed; no normalization or remapping is prescribed.",
        f"- bd has {numeric['bd']['non_integer_rows']:,} non-integer rows and the numeric "
        "threshold counts above. Validate its meaning and quality before treating it "
        "as an analytical age. Zero, negative values, and high values were not altered.",
        "- Registration-date typing must account for the reported empty and invalid "
        "values. The inspection boundaries do not define acceptable business dates.",
        "- Final cleaning rules and SQL implementation are deferred; raw source values "
        "remain unchanged.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    temporary_path: Path | None = None
    try:
        report = build_report(scan_attributes(args.progress_every))
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=REPORT_PATH.parent,
            prefix=".member_attribute_analysis_", suffix=".tmp", delete=False,
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
