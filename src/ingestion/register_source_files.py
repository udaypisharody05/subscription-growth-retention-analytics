"""Register current KKBox raw-file fingerprints through the psql client."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_PATH = PROJECT_ROOT / "data/processed/inspection/source_file_fingerprints.json"
RAW_DIR = PROJECT_ROOT / "data/raw"
EXPECTED = {
    "members_v3.csv": ("data/raw/members_v3.csv", 427_921_437, 6_769_473),
    "train.csv": ("data/raw/train.csv", 46_667_771, 992_931),
    "train_v2.csv": ("data/raw/train_v2.csv", 45_635_134, 970_960),
    "transactions.csv": ("data/raw/transactions.csv", 1_729_298_376, 21_547_746),
    "transactions_v2.csv": ("data/raw/transactions_v2.csv", 115_394_513, 1_431_009),
    "user_logs.csv": ("data/raw/user_logs.csv", 30_514_081_415, 392_106_543),
    "user_logs_v2.csv": ("data/raw/user_logs_v2.csv", 1_431_465_728, 18_396_362),
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register KKBox source-file versions.")
    parser.add_argument("--database", default="subscription_growth_retention")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--psql-path", type=Path)
    parser.add_argument("--execute", action="store_true", help="Write registrations.")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    return args


def parse_aware_timestamp(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("file_modified_at must be a string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid file_modified_at: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("file_modified_at must include a timezone")
    return value


def validate_cache() -> list[dict[str, Any]]:
    with CACHE_PATH.open("r", encoding="utf-8") as cache_file:
        cache = json.load(cache_file)
    if not isinstance(cache, dict) or cache.get("version") != 1:
        raise ValueError("fingerprint cache version must be 1")
    files = cache.get("files")
    if not isinstance(files, dict) or set(files) != set(EXPECTED):
        missing = sorted(set(EXPECTED) - set(files or {}))
        extra = sorted(set(files or {}) - set(EXPECTED))
        raise ValueError(f"cache must contain exactly seven files; missing={missing}, extra={extra}")

    validated = []
    for name, (relative_path, expected_size, expected_rows) in EXPECTED.items():
        entry = files[name]
        if not isinstance(entry, dict) or entry.get("file_name") != name:
            raise ValueError(f"{name}: invalid file_name")
        if entry.get("relative_path") != relative_path:
            raise ValueError(f"{name}: invalid relative_path")
        if entry.get("file_size_bytes") != expected_size:
            raise ValueError(f"{name}: cached size differs from verified size")
        if entry.get("row_count") != expected_rows:
            raise ValueError(f"{name}: cached row count differs from verified count")
        if not isinstance(entry.get("sha256"), str) or not SHA256.fullmatch(entry["sha256"]):
            raise ValueError(f"{name}: sha256 must be 64 lowercase hexadecimal characters")
        parse_aware_timestamp(entry.get("file_modified_at"))
        if not isinstance(entry.get("file_modified_at_ns"), int):
            raise ValueError(f"{name}: file_modified_at_ns must be an integer")
        current = (RAW_DIR / name).stat()
        if current.st_size != expected_size or current.st_size != entry["file_size_bytes"]:
            raise ValueError(f"{name}: raw-file size is stale; fingerprinting is required")
        if current.st_mtime_ns != entry["file_modified_at_ns"]:
            raise ValueError(f"{name}: raw-file modification time is stale; fingerprinting is required")
        validated.append(entry)
    return validated


def discover_psql(explicit: Path | None) -> Path:
    if explicit is not None:
        candidate = explicit.resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f"psql executable not found: {candidate}")
        return candidate
    located = shutil.which("psql")
    if located:
        return Path(located).resolve()
    base = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "PostgreSQL"
    candidates = []
    for path in base.glob("*/bin/psql.exe"):
        try:
            version = tuple(int(part) for part in path.parents[1].name.split("."))
        except ValueError:
            continue
        candidates.append((version, path))
    if not candidates:
        raise FileNotFoundError("psql was not found on PATH or under Program Files/PostgreSQL")
    return max(candidates)[1].resolve()


def sql_literal(value: str) -> str:
    """Escape validated text as a PostgreSQL string literal."""
    if "\x00" in value:
        raise ValueError("PostgreSQL text values cannot contain NUL")
    return "'" + value.replace("'", "''") + "'"


def registration_sql(entries: list[dict[str, Any]]) -> str:
    value_rows = []
    checks = []
    for entry in entries:
        name = sql_literal(entry["file_name"])
        path = sql_literal(entry["relative_path"])
        modified = sql_literal(entry["file_modified_at"])
        digest = sql_literal(entry["sha256"])
        size = entry["file_size_bytes"]
        rows = entry["row_count"]
        value_rows.append(f"    ({name}, {path}, {size}, {rows}, {modified}::timestamptz, {digest})")
        checks.append(
            "    SELECT count(*) INTO matched FROM raw.source_file "
            f"WHERE relative_path = {path} AND file_size_bytes = {size} "
            f"AND sha256 = {digest} AND row_count = {rows};\n"
            f"    IF matched <> 1 THEN RAISE EXCEPTION 'Expected exactly one registration for %', {path}; END IF;\n"
            "    expected_matched := expected_matched + matched;"
        )
    values = ",\n".join(value_rows)
    return f"""BEGIN;
INSERT INTO raw.source_file
    (file_name, relative_path, file_size_bytes, row_count, file_modified_at, sha256)
VALUES
{values}
ON CONFLICT ON CONSTRAINT source_file_version_unique DO NOTHING;

DO $verify$
DECLARE
    matched BIGINT;
    expected_matched BIGINT := 0;
BEGIN
{chr(10).join(checks)}
    IF expected_matched <> 7 THEN
        RAISE EXCEPTION 'Expected fingerprint match count is not seven: %', expected_matched;
    END IF;
END;
$verify$;
COMMIT;
"""


def run() -> int:
    args = parse_args()
    try:
        entries = validate_cache()
        psql = discover_psql(args.psql_path)
        for entry in entries:
            print(
                f"{entry['file_name']}: {entry['file_size_bytes']:,} bytes, "
                f"{entry['row_count']:,} rows, {entry['sha256'][:12]}..."
            )
        print(f"psql: {psql}")
        if not args.execute:
            print("Dry run complete; PostgreSQL was not contacted.")
            return 0
        command = [
            str(psql), "-X", "-w", "-v", "ON_ERROR_STOP=1",
            "-h", args.host, "-p", str(args.port), "-U", args.user, "-d", args.database,
        ]
        environment = os.environ.copy()
        environment.setdefault("PGCONNECT_TIMEOUT", "10")
        completed = subprocess.run(
            command,
            input=registration_sql(entries),
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
        if completed.stdout:
            print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, end="")
        print("Seven source versions registered and transactionally verified.")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, MemoryError, RuntimeError) as exc:
        print(f"Registration failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
