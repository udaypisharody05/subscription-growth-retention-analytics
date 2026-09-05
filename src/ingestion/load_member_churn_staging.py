"""Bulk-load member and churn CSV sources into typed PostgreSQL staging tables."""

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
SOURCES = {
    "members_v3.csv": {
        "relative_path": "data/raw/members_v3.csv",
        "size": 427_921_437,
        "rows": 6_769_473,
        "destination": "members",
        "cohort": None,
    },
    "train.csv": {
        "relative_path": "data/raw/train.csv",
        "size": 46_667_771,
        "rows": 992_931,
        "destination": "churn_labels",
        "cohort": "2017-02-01",
    },
    "train_v2.csv": {
        "relative_path": "data/raw/train_v2.csv",
        "size": 45_635_134,
        "rows": 970_960,
        "destination": "churn_labels",
        "cohort": "2017-03-01",
    },
}
HEADERS = {
    "members_v3.csv": [
        "msno", "city", "bd", "gender", "registered_via", "registration_init_time"
    ],
    "train.csv": ["msno", "is_churn"],
    "train_v2.csv": ["msno", "is_churn"],
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load member and churn staging data.")
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
            if next(csv.reader(source_file), None) != HEADERS[name]:
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
        command, input=sql, text=True, encoding="utf-8", capture_output=True,
        env=environment, shell=False, check=False,
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
    statements = ["SELECT 'TOTAL','manifest',count(*),0,0,0 FROM raw.source_file;"]
    for entry in entries:
        table = entry["destination"]
        statements.append(
            f"SELECT 'SOURCE',{sql_literal(entry['file_name'])},sf.source_file_key,"
            f"count(s.source_row_number),COALESCE(min(s.source_row_number),0),"
            f"COALESCE(max(s.source_row_number),0),count(DISTINCT s.source_row_number) "
            f"FROM raw.source_file sf LEFT JOIN staging.{table} s "
            f"ON s.source_file_key=sf.source_file_key WHERE {manifest_predicate(entry)} "
            "GROUP BY sf.source_file_key;"
        )
    statements.extend([
        "SELECT 'TOTAL','members',count(*),0,0,0 FROM staging.members;",
        "SELECT 'TOTAL','churn_labels',count(*),0,0,0 FROM staging.churn_labels;",
        "SELECT 'TOTAL','transactions',count(*),0,0,0 FROM staging.transactions;",
    ])
    output = run_psql(command, "\n".join(statements))
    status: dict[str, Any] = {"sources": {}, "totals": {}}
    for line in output.splitlines():
        fields = line.split("|")
        if fields[0] == "TOTAL":
            status["totals"][fields[1]] = int(fields[2])
        elif fields[0] == "SOURCE":
            status["sources"][fields[1]] = tuple(int(value) for value in fields[2:])
    if status["totals"].get("manifest") != 7:
        raise ValueError("raw.source_file must contain exactly seven registered versions")
    if set(status["sources"]) != set(SOURCES):
        raise ValueError("each current fingerprint must match exactly one manifest row")
    for entry in entries:
        key, count, minimum, maximum, distinct = status["sources"][entry["file_name"]]
        expected = entry["rows"]
        if count not in (0, expected):
            raise ValueError(f"{entry['file_name']}: incomplete existing staging load ({count})")
        if count and (minimum, maximum, distinct) != (1, expected, expected):
            raise ValueError(f"{entry['file_name']}: inconsistent existing source-row lineage")
        entry["source_file_key"] = key
    expected_members = status["sources"]["members_v3.csv"][1]
    expected_churn = status["sources"]["train.csv"][1] + status["sources"]["train_v2.csv"][1]
    if status["totals"].get("members") != expected_members:
        raise ValueError("staging.members contains unexpected source rows")
    if status["totals"].get("churn_labels") != expected_churn:
        raise ValueError("staging.churn_labels contains unexpected source rows")
    if status["totals"].get("transactions") != 0:
        raise ValueError("staging.transactions must remain empty for this milestone")
    return status


def copy_path(name: str) -> str:
    path = (RAW_DIR / name).resolve().as_posix()
    return path.replace("'", "''")


def member_sql(entry: dict[str, Any]) -> str:
    key, expected = entry["source_file_key"], entry["rows"]
    return f"""BEGIN;
DO $$ BEGIN
 IF (SELECT count(*) FROM raw.source_file WHERE source_file_key={key} AND {manifest_predicate(entry)}) <> 1
 THEN RAISE EXCEPTION 'Manifest identity changed for members_v3.csv'; END IF;
END $$;
CREATE TEMP TABLE imported_members (
 source_row_number BIGINT GENERATED ALWAYS AS IDENTITY,
 msno TEXT, city TEXT, bd TEXT, gender TEXT, registered_via TEXT,
 registration_init_time TEXT
) ON COMMIT DROP;
\\copy imported_members (msno,city,bd,gender,registered_via,registration_init_time) FROM '{copy_path(entry['file_name'])}' WITH (FORMAT csv, HEADER true)
DO $$ BEGIN
 IF (SELECT count(*) FROM imported_members) <> {expected} THEN RAISE EXCEPTION 'Member COPY row count mismatch'; END IF;
 IF EXISTS (SELECT 1 FROM imported_members WHERE msno='' OR msno IS NULL
   OR city !~ '^[+-]?[0-9]+$' OR bd !~ '^[+-]?[0-9]+$'
   OR registered_via !~ '^[+-]?[0-9]+$'
   OR registration_init_time !~ '^[0-9]{{8}}$'
   OR to_char(to_date(registration_init_time,'YYYYMMDD'),'YYYYMMDD') <> registration_init_time)
 THEN RAISE EXCEPTION 'Member source validation failed'; END IF;
 IF (SELECT min(source_row_number)=1 AND max(source_row_number)={expected}
     AND count(DISTINCT source_row_number)={expected} FROM imported_members) IS NOT TRUE
 THEN RAISE EXCEPTION 'Member COPY lineage validation failed'; END IF;
END $$;
INSERT INTO staging.members
 (source_file_key,source_row_number,msno,city_code,bd_raw,gender,
  registered_via_code,registration_init_date)
SELECT {key},source_row_number,msno,city::INTEGER,bd::INTEGER,NULLIF(gender,''),
       registered_via::INTEGER,to_date(registration_init_time,'YYYYMMDD')
FROM imported_members
ON CONFLICT (source_file_key,source_row_number) DO NOTHING;
DO $$ BEGIN
 IF (SELECT count(*)={expected} AND min(source_row_number)=1 AND max(source_row_number)={expected}
     AND count(DISTINCT source_row_number)={expected} FROM staging.members WHERE source_file_key={key}) IS NOT TRUE
 THEN RAISE EXCEPTION 'Member staging verification failed'; END IF;
END $$;
COMMIT;
"""


def churn_sql(entry: dict[str, Any]) -> str:
    key, expected = entry["source_file_key"], entry["rows"]
    return f"""BEGIN;
DO $$ BEGIN
 IF (SELECT count(*) FROM raw.source_file WHERE source_file_key={key} AND {manifest_predicate(entry)}) <> 1
 THEN RAISE EXCEPTION 'Manifest identity changed for {entry['file_name']}'; END IF;
END $$;
CREATE TEMP TABLE imported_churn (
 source_row_number BIGINT GENERATED ALWAYS AS IDENTITY, msno TEXT, is_churn TEXT
) ON COMMIT DROP;
\\copy imported_churn (msno,is_churn) FROM '{copy_path(entry['file_name'])}' WITH (FORMAT csv, HEADER true)
DO $$ BEGIN
 IF (SELECT count(*) FROM imported_churn) <> {expected} THEN RAISE EXCEPTION 'Churn COPY row count mismatch'; END IF;
 IF EXISTS (SELECT 1 FROM imported_churn WHERE msno='' OR msno IS NULL OR is_churn NOT IN ('0','1'))
 THEN RAISE EXCEPTION 'Churn source validation failed'; END IF;
 IF (SELECT min(source_row_number)=1 AND max(source_row_number)={expected}
     AND count(DISTINCT source_row_number)={expected} FROM imported_churn) IS NOT TRUE
 THEN RAISE EXCEPTION 'Churn COPY lineage validation failed'; END IF;
END $$;
INSERT INTO staging.churn_labels
 (source_file_key,source_row_number,msno,is_churn,expiry_cohort_month)
SELECT {key},source_row_number,msno,(is_churn='1'),DATE {sql_literal(entry['cohort'])}
FROM imported_churn
ON CONFLICT (source_file_key,source_row_number) DO NOTHING;
DO $$ BEGIN
 IF (SELECT count(*)={expected} AND min(source_row_number)=1 AND max(source_row_number)={expected}
     AND count(DISTINCT source_row_number)={expected} FROM staging.churn_labels WHERE source_file_key={key}) IS NOT TRUE
 THEN RAISE EXCEPTION 'Churn staging verification failed for {entry['file_name']}'; END IF;
END $$;
COMMIT;
"""


def run() -> int:
    args = parse_args()
    try:
        entries = validate_sources()
        psql = discover_psql(args.psql_path)
        for entry in entries:
            cohort = entry["cohort"] or "N/A"
            print(f"{entry['file_name']} -> staging.{entry['destination']}: {entry['rows']:,} rows; cohort {cohort}")
        print(f"psql: {psql}")
        if not args.execute:
            print("Dry run complete; PostgreSQL was not contacted.")
            return 0

        command = command_for(args, psql)
        status = inspect_database(command, entries)
        for entry in entries:
            existing = status["sources"][entry["file_name"]][1]
            if existing == entry["rows"]:
                print(f"{entry['file_name']}: already completely loaded; skipped")
                continue
            print(f"{entry['file_name']}: loading {entry['rows']:,} rows", flush=True)
            sql = member_sql(entry) if entry["destination"] == "members" else churn_sql(entry)
            output = run_psql(command, sql)
            if output:
                print(output, end="")
            print(f"{entry['file_name']}: committed", flush=True)
        final_status = inspect_database(command, entries)
        if final_status["totals"]["members"] != SOURCES["members_v3.csv"]["rows"]:
            raise ValueError("final member total mismatch")
        if final_status["totals"]["churn_labels"] != 1_963_891:
            raise ValueError("final churn total mismatch")
        print("Member and churn staging loads are complete and verified.")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, MemoryError, RuntimeError) as exc:
        print(f"Staging load failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
