"""Stream transaction files to inspect field quality without cleaning records."""

from __future__ import annotations

import argparse
import csv
import html
import sys
import tempfile
from collections import Counter
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
REPORT_PATH = PROJECT_ROOT / "docs" / "transaction_field_analysis.md"
FILES = ("transactions.csv", "transactions_v2.csv")
COLUMNS = (
    "msno", "payment_method_id", "payment_plan_days", "plan_list_price",
    "actual_amount_paid", "is_auto_renew", "transaction_date",
    "membership_expire_date", "is_cancel",
)
INTEGER_COLUMNS = (
    ("payment_method_id", 1), ("payment_plan_days", 2), ("plan_list_price", 3),
    ("actual_amount_paid", 4), ("is_auto_renew", 5), ("is_cancel", 8),
)
DATE_COLUMNS = (("transaction_date", 6), ("membership_expire_date", 7))
FLAGS = ("is_auto_renew", "is_cancel")
QUANTILES = (
    ("p01", 1), ("p05", 5), ("p25", 25), ("median", 50),
    ("p75", 75), ("p95", 95), ("p99", 99),
)
EXTREME_EXPIRIES = {
    date(1970, 1, 1).toordinal(): "1970-01-01",
    date(2036, 10, 15).toordinal(): "2036-10-15",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect KKBox transaction-field quality.")
    parser.add_argument("--files", nargs="+", choices=FILES, help="Default: both files.")
    parser.add_argument(
        "--progress-every", type=int, default=1_000_000,
        help="Print progress every this many rows (default: 1,000,000).",
    )
    args = parser.parse_args()
    if args.progress_every <= 0:
        parser.error("--progress-every must be greater than zero")
    return args


@lru_cache(maxsize=8192)
def integer_value(value: str) -> int | None:
    digits = value[1:] if value.startswith(("+", "-")) else value
    if not digits or not digits.isascii() or not digits.isdigit():
        return None
    return int(value)


@lru_cache(maxsize=32768)
def calendar_value(value: str) -> tuple[int, int] | None:
    if not (len(value) == 8 and value.isascii() and value.isdigit()):
        return None
    try:
        parsed = date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None
    return parsed.toordinal(), parsed.year


def scan_file(path: Path, progress_every: int) -> dict[str, Any]:
    integer_value.cache_clear()
    calendar_value.cache_clear()
    result = {
        "rows": 0,
        "integers": {
            name: {"empty": 0, "non_integer": 0, "frequency": Counter()}
            for name, _ in INTEGER_COLUMNS
        },
        "dates": {
            name: {"empty": 0, "invalid": 0, "valid": 0,
                   "min": None, "max": None, "years": Counter()}
            for name, _ in DATE_COLUMNS
        },
        "flag_values": {name: Counter() for name in FLAGS},
        "joint_flags": Counter(),
        "invalid_monetary_rows": 0,
        "invalid_flag_rows": 0,
        "price": Counter(),
        "difference_min": None,
        "difference_max": None,
        "expiry_deltas": Counter(),
        "expiry_extremes": Counter(),
        "plan_comparison": Counter(),
        "cancelled_expiry": Counter(),
    }
    print(f"Scanning {path.name}", flush=True)
    # One source record at a time. Retain only attribute/relationship counters,
    # never customer identifiers, full rows, or a row-sized numeric array.
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.reader(csv_file, strict=True)
        header = next(reader, None)
        if header is None or tuple(header) != COLUMNS:
            raise ValueError(f"{path.name}: header differs from the exact expected schema/order")
        for row in reader:
            result["rows"] += 1
            if len(row) != len(COLUMNS):
                raise ValueError(f"{path.name}: malformed field count at data row {result['rows']}")
            numbers = []
            for name, index in INTEGER_COLUMNS:
                value = row[index]
                stats = result["integers"][name]
                parsed = integer_value(value) if value != "" else None
                if value == "":
                    stats["empty"] += 1
                elif parsed is None:
                    stats["non_integer"] += 1
                else:
                    stats["frequency"][parsed] += 1
                if name in FLAGS:
                    result["flag_values"][name][value] += 1
                numbers.append(parsed)
            _, plan_days, list_price, paid, auto_renew, cancel = numbers

            if list_price is None or paid is None:
                result["invalid_monetary_rows"] += 1
            else:
                checks = result["price"]
                checks["eligible"] += 1
                checks["equal"] += paid == list_price
                checks["less"] += paid < list_price
                checks["greater"] += paid > list_price
                checks["paid_zero_list_positive"] += paid == 0 and list_price > 0
                checks["list_zero_paid_positive"] += list_price == 0 and paid > 0
                checks["both_zero"] += paid == 0 and list_price == 0
                difference = list_price - paid
                if result["difference_min"] is None or difference < result["difference_min"]:
                    result["difference_min"] = difference
                if result["difference_max"] is None or difference > result["difference_max"]:
                    result["difference_max"] = difference

            if auto_renew in (0, 1) and cancel in (0, 1):
                result["joint_flags"][(auto_renew, cancel)] += 1
            else:
                result["invalid_flag_rows"] += 1

            ordinals = []
            for name, index in DATE_COLUMNS:
                value = row[index]
                stats = result["dates"][name]
                parsed_date = calendar_value(value) if value != "" else None
                if value == "":
                    stats["empty"] += 1
                elif parsed_date is None:
                    stats["invalid"] += 1
                else:
                    ordinal, year = parsed_date
                    stats["valid"] += 1
                    stats["years"][year] += 1
                    if stats["min"] is None or ordinal < stats["min"]:
                        stats["min"] = ordinal
                    if stats["max"] is None or ordinal > stats["max"]:
                        stats["max"] = ordinal
                ordinals.append(parsed_date[0] if parsed_date is not None else None)
            transaction_day, expiry_day = ordinals
            if expiry_day in EXTREME_EXPIRIES:
                result["expiry_extremes"][EXTREME_EXPIRIES[expiry_day]] += 1
            if transaction_day is not None and expiry_day is not None:
                delta = expiry_day - transaction_day
                result["expiry_deltas"][delta] += 1
                if plan_days is not None:
                    checks = result["plan_comparison"]
                    checks["eligible"] += 1
                    checks["equal"] += delta == plan_days
                    checks["less"] += delta < plan_days
                    checks["greater"] += delta > plan_days
                if cancel == 1:
                    category = "negative" if delta < 0 else ("zero" if delta == 0 else "positive")
                    result["cancelled_expiry"][category] += 1
            if result["rows"] % progress_every == 0:
                print(f"{path.name}: {result['rows']:,} rows processed", flush=True)
    integer_value.cache_clear()
    calendar_value.cache_clear()
    print(f"{path.name}: complete ({result['rows']:,} rows)", flush=True)
    return result


def weighted_quantiles(frequencies: Counter[int]) -> dict[str, str]:
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
        raise ValueError("Invalid weighted quantile rank")

    result = {}
    for label, percentile in QUANTILES:
        lower, remainder = divmod((total - 1) * percentile, 100)
        low = value_at(lower)
        high = value_at(lower + 1) if remainder else low
        hundredths = low * (100 - remainder) + high * remainder
        whole, fraction = divmod(abs(hundredths), 100)
        text = ("-" if hundredths < 0 else "") + str(whole)
        if fraction:
            text += "." + f"{fraction:02d}".rstrip("0")
        result[label] = text
    return result


def display(value: Any) -> str:
    if value is None:
        return "N/A"
    return f"{value:,}" if isinstance(value, int) else str(value)


def metric_table(items: Iterable[tuple[str, Any]]) -> list[str]:
    return ["| Metric | Value |", "| --- | ---: |"] + [
        f"| {label} | {display(value)} |" for label, value in items
    ]


def range_checks(frequency: Counter[int], cutoffs: tuple[int, ...]) -> list[tuple[str, Any]]:
    return [
        ("Numeric rows", sum(frequency.values())),
        ("Minimum", min(frequency) if frequency else None),
        ("Maximum", max(frequency) if frequency else None),
        ("Rows < 0", sum(n for value, n in frequency.items() if value < 0)),
        ("Rows = 0", frequency[0]),
        ("Rows > 0", sum(n for value, n in frequency.items() if value > 0)),
    ] + [(f"Rows > {cutoff}", sum(n for value, n in frequency.items() if value > cutoff))
         for cutoff in cutoffs]


def add_numeric_section(
    lines: list[str], results: dict[str, Any], field: str, heading: str,
    cutoffs: tuple[int, ...] = (), quantiles: bool = False,
) -> None:
    lines.extend(["", heading, ""])
    subheading = "#" * (len(heading.split()[0]) + 1)
    for name, result in results.items():
        frequency = result["integers"][field]["frequency"]
        lines.extend([f"{subheading} {name}", ""])
        lines.extend(metric_table(range_checks(frequency, cutoffs)))
        if quantiles:
            lines.extend(["", "Quantiles over numeric rows:", ""])
            lines.extend(metric_table(weighted_quantiles(frequency).items()))
        limit = 100 if field == "payment_method_id" else 20
        lines.extend(["", "| Numeric source value | Rows |", "| --- | ---: |"])
        lines.extend(f"| {value} | {count:,} |" for value, count in frequency.most_common(limit))
        if len(frequency) > limit:
            lines.extend(["", f"Top {limit} of {len(frequency):,} distinct numeric values shown; "
                          "all frequencies were calculated."])
        lines.append("")


def comparison_metrics(result: dict[str, Any]) -> dict[str, int]:
    days = result["integers"]["payment_plan_days"]
    return {
        "Rows": result["rows"],
        "Invalid payment_plan_days (empty/non-integer)": days["empty"] + days["non_integer"],
        "Invalid monetary rows (either field empty/non-integer)": result["invalid_monetary_rows"],
        "Invalid flag rows (either field empty/non-binary)": result["invalid_flag_rows"],
        "Invalid non-empty transaction dates": result["dates"]["transaction_date"]["invalid"],
        "Empty transaction dates": result["dates"]["transaction_date"]["empty"],
        "Invalid non-empty expiry dates": result["dates"]["membership_expire_date"]["invalid"],
        "Empty expiry dates": result["dates"]["membership_expire_date"]["empty"],
        "Negative expiry deltas": sum(n for delta, n in result["expiry_deltas"].items() if delta < 0),
        "Actual paid < list price": result["price"]["less"],
        "Actual paid > list price": result["price"]["greater"],
    }


def build_report(results: dict[str, Any]) -> str:
    missing = [name for name in FILES if name not in results]
    lines = [
        "# KKBox Transaction Field Analysis", "",
        "## Methodology", "",
        "Completed sources: " + ", ".join(results) + ".",
        "Unscanned sources: " + (", ".join(missing) if missing else "none") + ".",
        "",
        "- Files were scanned sequentially and kept separate. Exact column order and "
        "field counts were validated; no source rows were cleaned, deleted, or deduplicated.",
        "- Integer syntax is an optional single sign followed by ASCII digits. Empty "
        "fields are counted separately; decimals, whitespace-padded values, and malformed "
        "strings are not coerced. Frequencies and relationships use parsed integers.",
        "- Binary validity means a parsed integer equal to 0 or 1. Original flag strings "
        "are also frequency-counted, so alternative textual representations remain visible.",
        "- Dates require eight ASCII digits and full calendar validity. Bounded parser "
        "caches avoid repeatedly parsing common field values; they retain no customer IDs.",
        "- Numeric quantiles use exact frequency-weighted linear interpolation at "
        "zero-based position (N - 1) * p. Empty/non-integer values are excluded; date-delta "
        "quantiles require two valid dates. No row-sized arrays or sampling are used.",
        "- Cross-field checks include only rows with the required valid inputs. "
        "Monetary/flag summary failures count a row once even if both fields fail. "
        "Date invalid counts exclude empty fields, which are shown separately.",
        "- Threshold counts overlap. Negative/high values are inspection flags, not "
        "automatic invalidity judgments. Source code meanings and currency units are not inferred.",
        "- No identifiers, hashes, raw records, or sample customer records are reported.",
        "", "## Source Summary", "",
        "| Metric | transactions.csv | transactions_v2.csv |", "| --- | ---: | ---: |",
    ]
    comparisons = {name: comparison_metrics(result) for name, result in results.items()}
    for metric in next(iter(comparisons.values())):
        values = [display(comparisons[name][metric]) if name in comparisons else "Not scanned"
                  for name in FILES]
        lines.append(f"| {metric} | {values[0]} | {values[1]} |")
    lines.extend([
        "", "### Integer field parsing", "",
        "| Source | Field | Empty | Non-integer | Numeric rows | Distinct numeric | Min | Max |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for name, result in results.items():
        for field, _ in INTEGER_COLUMNS:
            stats = result["integers"][field]
            frequency = stats["frequency"]
            lines.append(
                f"| {name} | {field} | {stats['empty']:,} | {stats['non_integer']:,} | "
                f"{sum(frequency.values()):,} | {len(frequency):,} | "
                f"{display(min(frequency) if frequency else None)} | "
                f"{display(max(frequency) if frequency else None)} |"
            )

    add_numeric_section(lines, results, "payment_method_id", "## payment_method_id")
    add_numeric_section(lines, results, "payment_plan_days", "## payment_plan_days", (31, 365, 730), True)
    lines.extend(["", "## Monetary Fields"])
    add_numeric_section(lines, results, "plan_list_price", "### plan_list_price", quantiles=True)
    add_numeric_section(lines, results, "actual_amount_paid", "### actual_amount_paid", quantiles=True)
    lines.extend(["", "### Price Relationship", "",
                  "Derived price difference = plan_list_price minus actual_amount_paid. "
                  "This inspection difference is not an official discount measure."])
    for name, result in results.items():
        checks = result["price"]
        lines.extend(["", f"#### {name}", ""])
        lines.extend(metric_table([
            ("Rows with two valid monetary integers", checks["eligible"]),
            ("Actual paid = list price", checks["equal"]),
            ("Actual paid < list price", checks["less"]),
            ("Actual paid > list price", checks["greater"]),
            ("Actual paid = 0 and list price > 0", checks["paid_zero_list_positive"]),
            ("List price = 0 and actual paid > 0", checks["list_zero_paid_positive"]),
            ("Both prices = 0", checks["both_zero"]),
            ("Minimum derived price difference", result["difference_min"]),
            ("Maximum derived price difference", result["difference_max"]),
            ("Derived price difference > 0", checks["less"]),
            ("Derived price difference = 0", checks["equal"]),
            ("Derived price difference < 0", checks["greater"]),
        ]))

    lines.extend(["", "## Renewal and Cancellation Flags"])
    for field in FLAGS:
        lines.extend(["", f"### {field}"])
        for name, result in results.items():
            stats = result["integers"][field]
            frequency = stats["frequency"]
            outside = sum(n for value, n in frequency.items() if value not in (0, 1))
            lines.extend(["", f"#### {name}", ""])
            lines.extend(metric_table([
                ("Rows = 0 (parsed integer)", frequency[0]),
                ("Rows = 1 (parsed integer)", frequency[1]),
                ("Numeric rows outside {0,1}", outside),
                ("Non-empty rows outside valid binary {0,1}", outside + stats["non_integer"]),
                ("Empty rows", stats["empty"]), ("Non-integer rows", stats["non_integer"]),
            ]))
            lines.extend(["", "| Source value | Rows |", "| --- | ---: |"])
            for value, count in result["flag_values"][field].most_common():
                escaped = html.escape(value, quote=False).replace("|", "&#124;")
                escaped = escaped.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
                label = f"<code>{escaped}</code>" if value else "(empty field)"
                lines.append(f"| {label} | {count:,} |")
    lines.extend(["", "### Joint valid-binary matrix"])
    for name, result in results.items():
        lines.extend(["", f"#### {name}", "",
                      "| is_auto_renew | is_cancel | Rows |", "| --- | --- | ---: |"])
        for renew in (0, 1):
            for cancel in (0, 1):
                lines.append(f"| {renew} | {cancel} | {result['joint_flags'][(renew, cancel)]:,} |")

    for field, heading in (("transaction_date", "Transaction Dates"),
                           ("membership_expire_date", "Membership Expiry Dates")):
        lines.extend(["", f"## {heading}"])
        for name, result in results.items():
            stats = result["dates"][field]
            lines.extend(["", f"### {name}", ""])
            lines.extend(metric_table([
                ("Empty rows", stats["empty"]), ("Invalid non-empty rows", stats["invalid"]),
                ("Valid-date rows", stats["valid"]),
                ("Minimum valid date", date.fromordinal(stats["min"]) if stats["min"] else None),
                ("Maximum valid date", date.fromordinal(stats["max"]) if stats["max"] else None),
                ("Distinct valid years", len(stats["years"])),
            ]))
            lines.extend(["", "| Valid year | Rows |", "| --- | ---: |"])
            lines.extend(f"| {year} | {count:,} |" for year, count in sorted(stats["years"].items()))
            if field == "membership_expire_date":
                lines.extend([""] + metric_table([
                    (f"Expiry date = {value}", result["expiry_extremes"][value])
                    for value in EXTREME_EXPIRIES.values()
                ]))

    lines.extend(["", "## Transaction-to-Expiry Relationship", "",
                  "expiry_delta_days is membership_expire_date minus transaction_date, "
                  "using only rows with two valid dates. All values below are in days."])
    for name, result in results.items():
        frequency = result["expiry_deltas"]
        lines.extend(["", f"### {name}", ""])
        lines.extend(metric_table(range_checks(frequency, (31, 365, 730, 3650))))
        lines.extend(["", "Quantiles over valid date-pair rows:", ""])
        lines.extend(metric_table(weighted_quantiles(frequency).items()))

    lines.extend(["", "## Cross-Field Checks"])
    for name, result in results.items():
        plan = result["plan_comparison"]
        cancelled = result["cancelled_expiry"]
        lines.extend(["", f"### {name}", ""])
        lines.extend(metric_table([
            ("Rows with numeric plan days and two valid dates", plan["eligible"]),
            ("Expiry delta = payment_plan_days", plan["equal"]),
            ("Expiry delta < payment_plan_days", plan["less"]),
            ("Expiry delta > payment_plan_days", plan["greater"]),
            ("Cancelled rows (is_cancel = 1) with two valid dates", sum(cancelled.values())),
            ("Cancelled rows with expiry delta < 0", cancelled["negative"]),
            ("Cancelled rows with expiry delta = 0", cancelled["zero"]),
            ("Cancelled rows with expiry delta > 0", cancelled["positive"]),
        ]))

    lines.extend(["", "## Data Quality Findings", ""])
    for name, result in results.items():
        negative = sum(n for delta, n in result["expiry_deltas"].items() if delta < 0)
        large = sum(n for delta, n in result["expiry_deltas"].items() if delta > 3650)
        lines.extend([
            f"- {name}: {result['invalid_monetary_rows']:,} rows have at least one missing "
            f"or non-integer monetary field; {result['invalid_flag_rows']:,} rows have "
            "at least one missing or non-binary flag.",
            f"- {name}: actual paid is below list price in {result['price']['less']:,} rows "
            f"and above it in {result['price']['greater']:,} rows among "
            f"{result['price']['eligible']:,} valid monetary pairs.",
            f"- {name}: {negative:,} valid date pairs have negative expiry deltas and "
            f"{large:,} exceed 3,650 days. Expiry dates 1970-01-01 and 2036-10-15 occur "
            f"{result['expiry_extremes']['1970-01-01']:,} and "
            f"{result['expiry_extremes']['2036-10-15']:,} times respectively.",
        ])
    lines.extend([
        "", "## Implications for fact_transaction", "",
        "- Use the field-level parse counts and ranges to assess integer compatibility. "
        "Preserve raw source values alongside future typed values and explicit validation "
        "flags where needed; do not silently coerce or delete problematic records.",
        "- Assess binary compatibility from the complete flag frequencies. Cancellation "
        "is not churn, and the cancellation/date checks are descriptive only.",
        "- Zero and negative monetary values and differences from list price require "
        "interpretation before monetary business measures are defined. The derived price "
        "difference is not an official discount. Currency units, net revenue, MRR, and "
        "ARPU are not defined by this inspection.",
        "- Calendar validity is separate from date plausibility. Negative or large expiry "
        "deltas and the explicitly counted expiry extremes are candidates for validation "
        "flags, not automatic grounds for deletion. Plan days need not equal expiry delta.",
        "- Preserve both transaction files and source lineage. The verified zero exact "
        "full-row overlap does not justify customer/date deduplication or merging source "
        "records into one assumed business transaction.",
        "- No final cleaning rules or SQL are introduced.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    selected = list(dict.fromkeys(args.files or FILES))
    temporary_path: Path | None = None
    try:
        results = {}
        for name in selected:
            results[name] = scan_file(RAW_DATA_DIR / name, args.progress_every)
        report = build_report(results)
        if set(results) != set(FILES):
            print("\nSelected-source results only. The public report is unchanged.\n")
            print(report)
            return 0
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=REPORT_PATH.parent,
            prefix=".transaction_field_analysis_", suffix=".tmp", delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(report)
        temporary_path.replace(REPORT_PATH)
    except KeyboardInterrupt:
        print("\nAnalysis interrupted; no completed public report for this run.", file=sys.stderr)
        return 130
    except (OSError, ValueError, csv.Error, MemoryError) as exc:
        print(
            f"Analysis failed ({type(exc).__name__}): {exc}. "
            "No completed public report for this run.", file=sys.stderr,
        )
        return 1
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    print(f"Report written to: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
