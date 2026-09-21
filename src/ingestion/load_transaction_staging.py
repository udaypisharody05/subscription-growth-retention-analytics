"""Bulk-load KKBox transaction CSV sources into typed PostgreSQL staging."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from register_source_files import discover_psql, sql_literal


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_PATH = PROJECT_ROOT / "data/processed/inspection/source_file_fingerprints.json"
RAW_DIR = PROJECT_ROOT / "data/raw"
EXPECTED_MEMBERS = 6_769_473
EXPECTED_CHURN_LABELS = 1_963_891
EXPECTED_MANIFEST = 7
EXPECTED_TOTAL = 22_978_755
SOURCES = {
    "transactions.csv": {
        "relative_path": "data/raw/transactions.csv",
        "size": 1_729_298_376,
        "rows": 21_547_746,
        "metrics": {
            "cancel_false": 20_690_895,
            "cancel_true": 856_851,
            "negative_expiry": 153_660,
            "zero_expiry": 471_741,
            "long_expiry": 2_344,
            "over_3650_expiry": 0,
            "expiry_1970": 1_776,
            "expiry_2036": 0,
            "price_equal": 19_832_943,
            "paid_below_list": 857_381,
            "paid_above_list": 857_422,
            "plan_equal": 6_716_387,
            "expiry_shorter": 3_587_269,
            "expiry_longer": 11_244_090,
            "plan_days_zero": 870_124,
            "plan_days_30": 18_956_290,
            "plan_days_over_31": 326_729,
            "plan_days_over_365": 94_058,
            "list_price_zero": 1_498_544,
            "paid_zero": 1_196_876,
            "paid_zero_list_positive": 555_600,
            "list_zero_paid_positive": 857_268,
            "both_prices_zero": 641_276,
        },
    },
    "transactions_v2.csv": {
        "relative_path": "data/raw/transactions_v2.csv",
        "size": 115_394_513,
        "rows": 1_431_009,
        "metrics": {
            "cancel_false": 1_395_876,
            "cancel_true": 35_133,
            "negative_expiry": 5_106,
            "zero_expiry": 17_700,
            "long_expiry": 50_121,
            "over_3650_expiry": 49,
            "expiry_1970": 0,
            "expiry_2036": 1,
            "price_equal": 1_419_106,
            "paid_below_list": 9_639,
            "paid_above_list": 2_264,
            "plan_equal": 405_903,
            "expiry_shorter": 37_493,
            "expiry_longer": 987_613,
            "plan_days_zero": 2_218,
            "plan_days_30": 1_217_998,
            "plan_days_over_31": 197_427,
            "plan_days_over_365": 98_727,
            "list_price_zero": 18_413,
            "paid_zero": 21_448,
            "paid_zero_list_positive": 5_251,
            "list_zero_paid_positive": 2_216,
            "both_prices_zero": 16_197,
        },
    },
}
HEADER = [
    "msno",
    "payment_method_id",
    "payment_plan_days",
    "plan_list_price",
    "actual_amount_paid",
    "is_auto_renew",
    "transaction_date",
    "membership_expire_date",
    "is_cancel",
]
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load transaction staging data.")
    parser.add_argument("--database", default="subscription_growth_retention")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--psql-path", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    return args


def validate_timestamp(value: Any) -> None:
    if not isinstance(value, str):
        raise ValueError("file_modified_at must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("file_modified_at must be timezone-aware")


def validate_sources() -> list[dict[str, Any]]:
    with CACHE_PATH.open("r", encoding="utf-8") as cache_file:
        cache = json.load(cache_file)
    if not isinstance(cache, dict) or cache.get("version") != 1:
        raise ValueError("fingerprint cache version must be 1")
    files = cache.get("files")
    if not isinstance(files, dict):
        raise ValueError("fingerprint cache files must be an object")

    validated = []
    for name, expected in SOURCES.items():
        entry = files.get(name)
        if not isinstance(entry, dict) or entry.get("file_name") != name:
            raise ValueError(f"{name}: missing or invalid cache entry")
        if entry.get("relative_path") != expected["relative_path"]:
            raise ValueError(f"{name}: relative path mismatch")
        if entry.get("file_size_bytes") != expected["size"]:
            raise ValueError(f"{name}: verified size mismatch")
        if entry.get("row_count") != expected["rows"]:
            raise ValueError(f"{name}: verified row-count mismatch")
        if not isinstance(entry.get("sha256"), str) or not SHA256.fullmatch(entry["sha256"]):
            raise ValueError(f"{name}: invalid SHA-256")
        validate_timestamp(entry.get("file_modified_at"))
        if not isinstance(entry.get("file_modified_at_ns"), int):
            raise ValueError(f"{name}: file_modified_at_ns must be an integer")
        current = (RAW_DIR / name).stat()
        if current.st_size != expected["size"] or current.st_size != entry["file_size_bytes"]:
            raise ValueError(f"{name}: raw-file size is stale; fingerprinting is required")
        if current.st_mtime_ns != entry["file_modified_at_ns"]:
            raise ValueError(f"{name}: raw-file mtime is stale; fingerprinting is required")
        with (RAW_DIR / name).open("r", encoding="utf-8-sig", newline="") as source_file:
            if next(csv.reader(source_file), None) != HEADER:
                raise ValueError(f"{name}: CSV header differs from the expected schema")
        validated.append({**entry, **expected})
    return validated


def command_for(args: argparse.Namespace, psql: Path) -> list[str]:
    return [
        str(psql), "-X", "-w", "-v", "ON_ERROR_STOP=1", "-At", "-F", "|",
        "-h", args.host, "-p", str(args.port), "-U", args.user, "-d", args.database,
    ]


def run_psql(command: list[str], sql: str) -> str:
    environment = os.environ.copy()
    environment.setdefault("PGCONNECT_TIMEOUT", "10")
    completed = subprocess.run(
        command,
        input=sql,
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=environment,
        shell=False,
        check=False,
    )
    if completed.returncode != 0:
        if completed.stdout:
            print(completed.stdout, file=sys.stderr, end="")
        if completed.stderr:
            print(completed.stderr, file=sys.stderr, end="")
        raise RuntimeError(f"psql failed with exit code {completed.returncode}")
    if completed.stderr:
        print(completed.stderr, end="")
    return completed.stdout


def manifest_predicate(entry: dict[str, Any]) -> str:
    return (
        f"relative_path={sql_literal(entry['relative_path'])} "
        f"AND file_size_bytes={entry['file_size_bytes']} "
        f"AND sha256={sql_literal(entry['sha256'])}"
    )


def inspect_database(command: list[str], entries: list[dict[str, Any]]) -> dict[str, Any]:
    statements = [
        "SELECT 'TOTAL','manifest',count(*),0,0,0 FROM raw.source_file;",
        "SELECT 'TOTAL','members',count(*),0,0,0 FROM staging.members;",
        "SELECT 'TOTAL','churn_labels',count(*),0,0,0 FROM staging.churn_labels;",
        "SELECT 'TOTAL','transactions',count(*),0,0,0 FROM staging.transactions;",
    ]
    for entry in entries:
        statements.append(
            f"SELECT 'SOURCE',{sql_literal(entry['file_name'])},sf.source_file_key,"
            "count(t.source_row_number),COALESCE(min(t.source_row_number),0),"
            "COALESCE(max(t.source_row_number),0),count(DISTINCT t.source_row_number) "
            "FROM raw.source_file sf LEFT JOIN staging.transactions t "
            f"ON t.source_file_key=sf.source_file_key WHERE {manifest_predicate(entry)} "
            "GROUP BY sf.source_file_key;"
        )
    output = run_psql(command, "\n".join(statements))
    state: dict[str, Any] = {"sources": {}, "totals": {}}
    for line in output.splitlines():
        fields = line.split("|")
        if fields[0] == "TOTAL":
            state["totals"][fields[1]] = int(fields[2])
        elif fields[0] == "SOURCE":
            state["sources"][fields[1]] = tuple(int(value) for value in fields[2:])

    if state["totals"].get("manifest") != EXPECTED_MANIFEST:
        raise ValueError("raw.source_file must contain exactly seven registered versions")
    if state["totals"].get("members") != EXPECTED_MEMBERS:
        raise ValueError("staging.members changed from its validated milestone count")
    if state["totals"].get("churn_labels") != EXPECTED_CHURN_LABELS:
        raise ValueError("staging.churn_labels changed from its validated milestone count")
    if set(state["sources"]) != set(SOURCES):
        raise ValueError("each transaction fingerprint must match exactly one manifest row")

    represented = 0
    for entry in entries:
        key, count, minimum, maximum, distinct = state["sources"][entry["file_name"]]
        expected = entry["rows"]
        if count not in (0, expected):
            raise ValueError(f"{entry['file_name']}: incomplete existing staging load ({count})")
        if count and (minimum, maximum, distinct) != (1, expected, expected):
            raise ValueError(f"{entry['file_name']}: inconsistent existing source-row lineage")
        represented += count
        entry["source_file_key"] = key
    if state["totals"].get("transactions") != represented:
        raise ValueError("staging.transactions contains rows from an unexpected source version")
    return state


def copy_path(name: str) -> str:
    return (RAW_DIR / name).resolve().as_posix().replace("'", "''")


def transaction_sql(entry: dict[str, Any]) -> str:
    key, expected = entry["source_file_key"], entry["rows"]
    name = entry["file_name"]
    return f"""BEGIN;
DO $$ BEGIN
 IF (SELECT count(*) FROM raw.source_file WHERE source_file_key={key} AND {manifest_predicate(entry)}) <> 1
 THEN RAISE EXCEPTION 'Manifest identity changed for {name}'; END IF;
END $$;
CREATE TEMP TABLE imported_transactions (
 source_row_number BIGINT GENERATED ALWAYS AS IDENTITY,
 msno TEXT, payment_method_id TEXT, payment_plan_days TEXT, plan_list_price TEXT,
 actual_amount_paid TEXT, is_auto_renew TEXT, transaction_date TEXT,
 membership_expire_date TEXT, is_cancel TEXT
) ON COMMIT DROP;
\\copy imported_transactions (msno,payment_method_id,payment_plan_days,plan_list_price,actual_amount_paid,is_auto_renew,transaction_date,membership_expire_date,is_cancel) FROM '{copy_path(name)}' WITH (FORMAT csv, HEADER true)
DO $$ BEGIN
 IF (SELECT count(*) FROM imported_transactions) <> {expected}
 THEN RAISE EXCEPTION 'Transaction COPY row count mismatch for {name}'; END IF;
 IF EXISTS (
   SELECT 1 FROM imported_transactions WHERE msno='' OR msno IS NULL
   OR payment_method_id !~ '^[+-]?[0-9]+$'
   OR payment_plan_days !~ '^[+-]?[0-9]+$'
   OR plan_list_price !~ '^[+-]?[0-9]+$'
   OR actual_amount_paid !~ '^[+-]?[0-9]+$'
   OR is_auto_renew NOT IN ('0','1') OR is_cancel NOT IN ('0','1')
   OR transaction_date !~ '^[0-9]{{8}}$'
   OR membership_expire_date !~ '^[0-9]{{8}}$'
   OR to_char(to_date(transaction_date,'YYYYMMDD'),'YYYYMMDD') <> transaction_date
   OR to_char(to_date(membership_expire_date,'YYYYMMDD'),'YYYYMMDD') <> membership_expire_date
 ) THEN RAISE EXCEPTION 'Transaction source validation failed for {name}'; END IF;
 IF (SELECT min(source_row_number)=1 AND max(source_row_number)={expected}
     AND count(DISTINCT source_row_number)={expected} FROM imported_transactions) IS NOT TRUE
 THEN RAISE EXCEPTION 'Transaction COPY lineage validation failed for {name}'; END IF;
END $$;
INSERT INTO staging.transactions (
 source_file_key,source_row_number,msno,payment_method_id,payment_plan_days,
 plan_list_price,actual_amount_paid,is_auto_renew,transaction_date,
 membership_expire_date,is_cancel
)
SELECT {key},source_row_number,msno,payment_method_id::INTEGER,
       payment_plan_days::INTEGER,plan_list_price::INTEGER,
       actual_amount_paid::INTEGER,(is_auto_renew='1'),
       to_date(transaction_date,'YYYYMMDD'),
       to_date(membership_expire_date,'YYYYMMDD'),(is_cancel='1')
FROM imported_transactions
ON CONFLICT (source_file_key,source_row_number) DO NOTHING;
DO $$ BEGIN
 IF (SELECT count(*)={expected} AND min(source_row_number)=1
     AND max(source_row_number)={expected}
     AND count(DISTINCT source_row_number)={expected}
     FROM staging.transactions WHERE source_file_key={key}) IS NOT TRUE
 THEN RAISE EXCEPTION 'Transaction staging verification failed for {name}'; END IF;
END $$;
COMMIT;
"""


def metric_sql(entry: dict[str, Any]) -> str:
    key = entry["source_file_key"]
    name = sql_literal(entry["file_name"])
    return f"""SELECT 'METRIC',{name},
 count(*) FILTER (WHERE NOT is_cancel),
 count(*) FILTER (WHERE is_cancel),
 count(*) FILTER (WHERE has_negative_expiry_delta),
 count(*) FILTER (WHERE has_zero_expiry_delta),
 count(*) FILTER (WHERE has_long_expiry_delta),
 count(*) FILTER (WHERE expiry_delta_days > 3650),
 count(*) FILTER (WHERE membership_expire_date=DATE '1970-01-01'),
 count(*) FILTER (WHERE membership_expire_date=DATE '2036-10-15'),
 count(*) FILTER (WHERE price_relationship='equal'),
 count(*) FILTER (WHERE price_relationship='paid_below_list'),
 count(*) FILTER (WHERE price_relationship='paid_above_list'),
 count(*) FILTER (WHERE plan_expiry_relationship='equal'),
 count(*) FILTER (WHERE plan_expiry_relationship='expiry_shorter'),
 count(*) FILTER (WHERE plan_expiry_relationship='expiry_longer'),
 count(*) FILTER (WHERE payment_plan_days=0),
 count(*) FILTER (WHERE payment_plan_days=30),
 count(*) FILTER (WHERE payment_plan_days>31),
 count(*) FILTER (WHERE payment_plan_days>365),
 count(*) FILTER (WHERE plan_list_price=0),
 count(*) FILTER (WHERE actual_amount_paid=0),
 count(*) FILTER (WHERE actual_amount_paid=0 AND plan_list_price>0),
 count(*) FILTER (WHERE plan_list_price=0 AND actual_amount_paid>0),
 count(*) FILTER (WHERE plan_list_price=0 AND actual_amount_paid=0),
 count(*) FILTER (WHERE msno IS NULL OR payment_method_id IS NULL
   OR payment_plan_days IS NULL OR plan_list_price IS NULL
   OR actual_amount_paid IS NULL OR is_auto_renew IS NULL
   OR transaction_date IS NULL OR membership_expire_date IS NULL
   OR is_cancel IS NULL),
 count(*) FILTER (WHERE price_difference IS NULL OR price_relationship IS NULL
   OR expiry_delta_days IS NULL OR has_negative_expiry_delta IS NULL
   OR has_zero_expiry_delta IS NULL OR has_long_expiry_delta IS NULL
   OR plan_expiry_relationship IS NULL),
 count(*) FILTER (WHERE price_difference <> plan_list_price-actual_amount_paid
   OR price_relationship <> CASE WHEN actual_amount_paid=plan_list_price THEN 'equal'
      WHEN actual_amount_paid<plan_list_price THEN 'paid_below_list' ELSE 'paid_above_list' END
   OR expiry_delta_days <> membership_expire_date-transaction_date
   OR has_negative_expiry_delta IS DISTINCT FROM (membership_expire_date-transaction_date<0)
   OR has_zero_expiry_delta IS DISTINCT FROM (membership_expire_date-transaction_date=0)
   OR has_long_expiry_delta IS DISTINCT FROM (membership_expire_date-transaction_date>730)
   OR plan_expiry_relationship <> CASE
      WHEN membership_expire_date-transaction_date=payment_plan_days THEN 'equal'
      WHEN membership_expire_date-transaction_date<payment_plan_days THEN 'expiry_shorter'
      ELSE 'expiry_longer' END)
FROM staging.transactions WHERE source_file_key={key};"""


def verify_full_load(command: list[str], entries: list[dict[str, Any]]) -> None:
    metric_names = [
        "cancel_false", "cancel_true", "negative_expiry", "zero_expiry",
        "long_expiry", "over_3650_expiry", "expiry_1970", "expiry_2036",
        "price_equal", "paid_below_list", "paid_above_list", "plan_equal",
        "expiry_shorter", "expiry_longer", "plan_days_zero", "plan_days_30",
        "plan_days_over_31", "plan_days_over_365", "list_price_zero", "paid_zero",
        "paid_zero_list_positive", "list_zero_paid_positive", "both_prices_zero",
        "required_nulls", "generated_nulls", "generated_mismatches",
    ]
    output = run_psql(command, "\n".join(metric_sql(entry) for entry in entries))
    found: dict[str, dict[str, int]] = {}
    for line in output.splitlines():
        fields = line.split("|")
        if fields[0] == "METRIC":
            found[fields[1]] = dict(zip(metric_names, map(int, fields[2:]), strict=True))
    if set(found) != set(SOURCES):
        raise ValueError("full transaction verification did not return both sources")
    for entry in entries:
        name = entry["file_name"]
        expected = {**entry["metrics"], "required_nulls": 0, "generated_nulls": 0,
                    "generated_mismatches": 0}
        if found[name] != expected:
            differences = {
                metric: (expected[metric], found[name].get(metric))
                for metric in expected if found[name].get(metric) != expected[metric]
            }
            raise ValueError(f"{name}: documented metric mismatch: {differences}")
        print(f"{name}: documented anomaly and distribution counts verified")


def run() -> int:
    args = parse_args()
    try:
        entries = validate_sources()
        psql = discover_psql(args.psql_path)
        for entry in entries:
            print(f"{entry['file_name']} -> staging.transactions: {entry['rows']:,} rows")
        print(f"psql: {psql}")
        if not args.execute:
            print("Dry run complete; PostgreSQL was not contacted.")
            return 0

        command = command_for(args, psql)
        initial = inspect_database(command, entries)
        loaded_any = False
        for entry in entries:
            existing = initial["sources"][entry["file_name"]][1]
            if existing == entry["rows"]:
                print(f"{entry['file_name']}: already completely loaded; skipped")
                continue
            print(f"{entry['file_name']}: loading {entry['rows']:,} rows", flush=True)
            output = run_psql(command, transaction_sql(entry))
            if output:
                print(output, end="")
            loaded_any = True
            print(f"{entry['file_name']}: committed", flush=True)

        final = inspect_database(command, entries)
        if final["totals"]["transactions"] != EXPECTED_TOTAL:
            raise ValueError("final transaction total mismatch")
        for entry in entries:
            if final["sources"][entry["file_name"]][1:] != (
                entry["rows"], 1, entry["rows"], entry["rows"]
            ):
                raise ValueError(f"{entry['file_name']}: final lineage mismatch")

        if loaded_any:
            verify_full_load(command, entries)
            print("Transaction staging load and full verification are complete.")
        else:
            print("Idempotence verified: no rows inserted; total remains 22,978,755.")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, MemoryError, RuntimeError) as exc:
        print(f"Transaction staging load failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
