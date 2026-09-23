"""Build bounded-memory daily KKBox activity aggregates from raw user logs.

Raw activity rows are never loaded into PostgreSQL or retained in full. The
pipeline aggregates bounded CSV chunks, writes monthly partials, and uses a
disk-backed DuckDB database to merge keys that recur across chunks or files.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import sys
import tempfile
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "user_activity"
SOURCE_NAMES = ("user_logs.csv", "user_logs_v2.csv")
COUNT_FIELDS = ("num_25", "num_50", "num_75", "num_985", "num_100", "num_unq")
EXPECTED_HEADER = ("msno", "date", *COUNT_FIELDS, "total_secs")
OUTPUT_HEADER = (
    "msno",
    "activity_date",
    *COUNT_FIELDS,
    "total_secs",
    "source_record_count",
)
MANIFEST_VERSION = 1
DATE_PATTERN = re.compile(r"^\d{8}$")
INTEGER_PATTERN = re.compile(r"^[+-]?\d+$")
MEMORY_LIMIT_PATTERN = re.compile(r"^\d+(?:MB|GB)$", re.IGNORECASE)
HUGEINT_MIN = -(2**127)
HUGEINT_MAX = 2**127 - 1
DECIMAL_MAX_INTEGER_DIGITS = 26
DECIMAL_SCALE = 12


@dataclass
class Aggregate:
    counts: list[int] = field(default_factory=lambda: [0] * len(COUNT_FIELDS))
    total_secs: Decimal = Decimal(0)
    source_record_count: int = 0

    def add(self, counts: list[int], total_secs: Decimal) -> None:
        for index, value in enumerate(counts):
            self.counts[index] += value
        self.total_secs += total_secs
        self.source_record_count += 1


@dataclass(frozen=True)
class PipelineConfig:
    files: tuple[Path, ...]
    output_dir: Path
    chunk_rows: int = 500_000
    progress_every: int = 100_000
    max_rows: int | None = None
    duckdb_memory_limit: str = "2GB"
    resume: bool = False
    restart: bool = False
    keep_partials: bool = False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def empty_totals() -> dict[str, int | str]:
    return {**{name: 0 for name in COUNT_FIELDS}, "total_secs": "0"}


def decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def add_totals(target: dict[str, Any], counts: Iterable[int], total_secs: Decimal) -> None:
    for name, value in zip(COUNT_FIELDS, counts):
        target[name] = int(target[name]) + value
    target["total_secs"] = decimal_text(Decimal(str(target["total_secs"])) + total_secs)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def relative_display(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def source_metadata(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": relative_display(path),
        "size_bytes": stat.st_size,
        "modified_time_ns": stat.st_mtime_ns,
    }


def config_signature(config: PipelineConfig) -> dict[str, Any]:
    return {
        "files": [relative_display(path) for path in config.files],
        "chunk_rows": config.chunk_rows,
        "max_rows_per_file": config.max_rows,
        "duckdb_memory_limit": config.duckdb_memory_limit.upper(),
        "decimal_scale": DECIMAL_SCALE,
    }


def new_manifest(config: PipelineConfig) -> dict[str, Any]:
    return {
        "version": MANIFEST_VERSION,
        "status": "in_progress",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "configuration": config_signature(config),
        "sources": {},
        "partitions": {},
        "reconciliation": {},
    }


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("version") != MANIFEST_VERSION:
        raise ValueError(f"Unsupported manifest version in {path}")
    return manifest


def prepare_run(config: PipelineConfig) -> tuple[dict[str, Any], Path]:
    manifest_path = config.output_dir / "manifests" / "processing_manifest.json"
    if config.restart and config.output_dir.exists():
        # Delete only this pipeline's known children. Never recursively delete a
        # caller-selected directory itself because it may contain unrelated work.
        for child_name in ("partials", "daily", "work", "manifests"):
            child = (config.output_dir / child_name).resolve()
            if child.parent != config.output_dir.resolve():
                raise ValueError(f"Unsafe restart target: {child}")
            if child.is_dir():
                shutil.rmtree(child)
            elif child.exists():
                child.unlink()
    if manifest_path.exists():
        if not config.resume:
            raise ValueError(
                f"Output already has a manifest: {manifest_path}. "
                "Use --resume or --restart."
            )
        manifest = load_manifest(manifest_path)
        if manifest.get("configuration") != config_signature(config):
            raise ValueError("Resume configuration does not match the existing manifest")
    else:
        if config.resume:
            raise ValueError(f"No manifest exists to resume: {manifest_path}")
        manifest = new_manifest(config)
        atomic_write_json(manifest_path, manifest)
    return manifest, manifest_path


def validate_header(reader: csv.DictReader, path: Path) -> None:
    actual = tuple(reader.fieldnames or ())
    if actual != EXPECTED_HEADER:
        raise ValueError(
            f"Unexpected header in {path}: expected {EXPECTED_HEADER}, got {actual}"
        )


def parse_activity_row(row: dict[str | None, Any]) -> tuple[str, str, list[int], Decimal] | str:
    if None in row or any(value is None for value in row.values()):
        return "malformed_csv_row"
    msno = row["msno"]
    if not msno or not msno.strip():
        return "empty_msno"
    raw_date = row["date"]
    if not DATE_PATTERN.fullmatch(raw_date):
        return "invalid_date"
    try:
        parsed_date = date(
            int(raw_date[0:4]), int(raw_date[4:6]), int(raw_date[6:8])
        )
    except ValueError:
        return "invalid_date"

    counts: list[int] = []
    for name in COUNT_FIELDS:
        raw_value = row[name]
        if not INTEGER_PATTERN.fullmatch(raw_value):
            return f"invalid_{name}"
        value = int(raw_value)
        if not HUGEINT_MIN <= value <= HUGEINT_MAX:
            return f"out_of_range_{name}"
        counts.append(value)

    try:
        total_secs = Decimal(row["total_secs"])
    except (InvalidOperation, ValueError):
        return "invalid_total_secs"
    if not total_secs.is_finite():
        return "invalid_total_secs"
    normalized = total_secs.as_tuple()
    scale = max(0, -normalized.exponent)
    integer_digits = max(1, len(normalized.digits) + normalized.exponent)
    if scale > DECIMAL_SCALE or integer_digits > DECIMAL_MAX_INTEGER_DIGITS:
        return "out_of_range_total_secs"
    return msno, parsed_date.isoformat(), counts, total_secs


def new_source_entry(path: Path) -> dict[str, Any]:
    return {
        "source": source_metadata(path),
        "status": "in_progress",
        "rows_read": 0,
        "valid_rows": 0,
        "invalid_rows": 0,
        "invalid_reasons": {},
        "minimum_valid_date": None,
        "maximum_valid_date": None,
        "input_metric_totals": empty_totals(),
        "chunks_completed": 0,
    }


def write_chunk_partials(
    chunk: dict[tuple[str, str], Aggregate],
    source_stem: str,
    chunk_number: int,
    partial_root: Path,
) -> set[str]:
    by_month: dict[str, list[tuple[tuple[str, str], Aggregate]]] = defaultdict(list)
    for key, aggregate in chunk.items():
        by_month[key[1][:7]].append((key, aggregate))

    months: set[str] = set()
    for month, rows in by_month.items():
        month_dir = partial_root / f"month={month}"
        month_dir.mkdir(parents=True, exist_ok=True)
        final_path = month_dir / f"{source_stem}.chunk-{chunk_number:06d}.csv"
        temp_path = final_path.with_suffix(".csv.tmp")
        with temp_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(OUTPUT_HEADER)
            # DuckDB performs the final ordering. Sorting every bounded partial
            # adds CPU work without contributing to correctness or resumability.
            for (msno, activity_date), aggregate in rows:
                writer.writerow(
                    [msno, activity_date, *aggregate.counts,
                     decimal_text(aggregate.total_secs), aggregate.source_record_count]
                )
        os.replace(temp_path, final_path)
        months.add(month)
    return months


def process_source(
    path: Path,
    config: PipelineConfig,
    manifest: dict[str, Any],
    manifest_path: Path,
) -> None:
    source_key = relative_display(path)
    current_metadata = source_metadata(path)
    entry = manifest["sources"].get(source_key)
    if entry:
        if entry.get("source") != current_metadata:
            raise ValueError(f"Source metadata changed; cannot resume safely: {path}")
        if entry.get("status") == "complete":
            print(f"Skipping completed source {path.name}")
            return
    else:
        entry = new_source_entry(path)
        manifest["sources"][source_key] = entry
        manifest["updated_at"] = utc_now()
        atomic_write_json(manifest_path, manifest)

    rows_to_skip = int(entry["rows_read"])
    chunk_number = int(entry["chunks_completed"])
    invalid_reasons = Counter(entry.get("invalid_reasons", {}))
    partial_root = config.output_dir / "partials"
    print(f"Processing {path.name} (resuming after {rows_to_skip:,} rows)")
    started = time.monotonic()
    next_progress = ((rows_to_skip // config.progress_every) + 1) * config.progress_every

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        validate_header(reader, path)
        for skipped in range(rows_to_skip):
            if next(reader, None) is None:
                raise ValueError(
                    f"Cannot resume {path.name}: source ended while skipping row {skipped + 1}"
                )

        reached_limit = config.max_rows is not None and rows_to_skip >= config.max_rows
        while not reached_limit:
            chunk: dict[tuple[str, str], Aggregate] = {}
            chunk_rows = 0
            chunk_valid = 0
            chunk_invalid = 0
            chunk_count_totals = [0] * len(COUNT_FIELDS)
            chunk_total_secs = Decimal(0)
            chunk_min_date: str | None = None
            chunk_max_date: str | None = None

            while chunk_rows < config.chunk_rows:
                if config.max_rows is not None and int(entry["rows_read"]) + chunk_rows >= config.max_rows:
                    reached_limit = True
                    break
                try:
                    row = next(reader)
                except StopIteration:
                    reached_limit = True
                    break
                except csv.Error:
                    chunk_rows += 1
                    chunk_invalid += 1
                    invalid_reasons["malformed_csv_row"] += 1
                    continue

                chunk_rows += 1
                parsed = parse_activity_row(row)
                if isinstance(parsed, str):
                    chunk_invalid += 1
                    invalid_reasons[parsed] += 1
                else:
                    msno, activity_date, counts, total_secs = parsed
                    aggregate = chunk.setdefault((msno, activity_date), Aggregate())
                    aggregate.add(counts, total_secs)
                    chunk_valid += 1
                    for index, value in enumerate(counts):
                        chunk_count_totals[index] += value
                    chunk_total_secs += total_secs
                    chunk_min_date = min(chunk_min_date or activity_date, activity_date)
                    chunk_max_date = max(chunk_max_date or activity_date, activity_date)

                absolute_rows = int(entry["rows_read"]) + chunk_rows
                if absolute_rows >= next_progress:
                    elapsed = max(time.monotonic() - started, 0.001)
                    print(
                        f"{path.name}: {absolute_rows:,} rows read "
                        f"({absolute_rows / elapsed:,.0f} rows/s)"
                    )
                    next_progress += config.progress_every

            if chunk_rows == 0:
                break

            chunk_number += 1
            months = write_chunk_partials(chunk, path.stem, chunk_number, partial_root)
            entry["rows_read"] += chunk_rows
            entry["valid_rows"] += chunk_valid
            entry["invalid_rows"] += chunk_invalid
            entry["invalid_reasons"] = dict(sorted(invalid_reasons.items()))
            entry["chunks_completed"] = chunk_number
            if chunk_min_date:
                entry["minimum_valid_date"] = min(
                    entry["minimum_valid_date"] or chunk_min_date, chunk_min_date
                )
                entry["maximum_valid_date"] = max(
                    entry["maximum_valid_date"] or chunk_max_date, chunk_max_date
                )
            add_totals(
                entry["input_metric_totals"],
                chunk_count_totals,
                chunk_total_secs,
            )
            for month in months:
                manifest["partitions"].setdefault(month, {"status": "pending"})
            manifest["updated_at"] = utc_now()
            atomic_write_json(manifest_path, manifest)
            del chunk

    entry["status"] = "complete"
    entry["completed_at"] = utc_now()
    manifest["updated_at"] = utc_now()
    atomic_write_json(manifest_path, manifest)
    print(
        f"Completed {path.name}: {entry['rows_read']:,} rows, "
        f"{entry['valid_rows']:,} valid, {entry['invalid_rows']:,} invalid"
    )


def sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def duckdb_columns() -> str:
    columns = ["'msno': 'VARCHAR'", "'activity_date': 'DATE'"]
    columns.extend(f"'{name}': 'HUGEINT'" for name in COUNT_FIELDS)
    columns.extend(
        [f"'total_secs': 'DECIMAL(38,{DECIMAL_SCALE})'", "'source_record_count': 'HUGEINT'"]
    )
    return "{" + ", ".join(columns) + "}"


def aggregate_manifest_inputs(manifest: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    valid_rows = 0
    totals = empty_totals()
    for entry in manifest["sources"].values():
        valid_rows += int(entry["valid_rows"])
        add_totals(
            totals,
            [int(entry["input_metric_totals"][name]) for name in COUNT_FIELDS],
            Decimal(str(entry["input_metric_totals"]["total_secs"])),
        )
    return valid_rows, totals


def consolidate_partition(
    month: str,
    config: PipelineConfig,
    manifest: dict[str, Any],
    manifest_path: Path,
) -> None:
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("DuckDB is required; install requirements.txt") from exc

    partial_dir = config.output_dir / "partials" / f"month={month}"
    partials = sorted(partial_dir.glob("*.csv"))
    partition = manifest["partitions"].setdefault(month, {"status": "pending"})
    final_dir = config.output_dir / "daily" / f"month={month}"
    final_path = final_dir / f"activity_daily_{month}.csv"
    if partition.get("status") == "complete" and final_path.exists():
        print(f"Skipping completed partition {month}")
        return
    if not partials:
        raise ValueError(f"No partial files available for incomplete partition {month}")

    work_dir = config.output_dir / "work"
    temp_dir = work_dir / "duckdb_temp" / month
    work_dir.mkdir(parents=True, exist_ok=True)
    # A failed consolidation can leave spill files. They are safe to discard
    # because monthly partials remain the authoritative resumable input.
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    database_path = work_dir / f"activity-{month}.duckdb"
    if database_path.exists():
        database_path.unlink()

    glob_path = (partial_dir / "*.csv").as_posix()
    print(f"Consolidating {month} from {len(partials):,} partial files")
    connection = duckdb.connect(str(database_path))
    try:
        connection.execute(
            f"SET memory_limit = {sql_quote(config.duckdb_memory_limit.upper())}"
        )
        connection.execute("SET threads = 1")
        connection.execute("SET preserve_insertion_order = false")
        connection.execute(f"SET temp_directory = {sql_quote(temp_dir.as_posix())}")
        sums = ",\n                ".join(
            [f"SUM({name})::HUGEINT AS {name}" for name in COUNT_FIELDS]
            + [
                f"SUM(total_secs)::DECIMAL(38,{DECIMAL_SCALE}) AS total_secs",
                "SUM(source_record_count)::HUGEINT AS source_record_count",
            ]
        )
        connection.execute(
            f"""
            CREATE TABLE daily AS
            SELECT msno, activity_date, {sums}
            FROM read_csv(
                {sql_quote(glob_path)}, header = true,
                columns = {duckdb_columns()}
            )
            GROUP BY msno, activity_date
            """
        )
        metric_select = ", ".join(
            [f"SUM({name})" for name in COUNT_FIELDS]
            + ["SUM(total_secs)", "SUM(source_record_count)"]
        )
        result = connection.execute(
            f"SELECT COUNT(*), MIN(activity_date), MAX(activity_date), {metric_select} FROM daily"
        ).fetchone()
        if result is None:
            raise RuntimeError(f"No consolidation result for {month}")

        daily_rows = int(result[0])
        output_totals = {
            **{name: int(result[index + 3] or 0) for index, name in enumerate(COUNT_FIELDS)},
            "total_secs": decimal_text(Decimal(str(result[3 + len(COUNT_FIELDS)] or 0))),
        }
        source_record_count = int(result[4 + len(COUNT_FIELDS)] or 0)
        final_dir.mkdir(parents=True, exist_ok=True)
        temp_output = final_path.with_suffix(".csv.tmp")
        select_fields = ", ".join(OUTPUT_HEADER)
        connection.execute(
            f"COPY (SELECT {select_fields} FROM daily ORDER BY activity_date, msno) "
            f"TO {sql_quote(temp_output.as_posix())} (HEADER, DELIMITER ',')"
        )
        os.replace(temp_output, final_path)

        file_check = connection.execute(
            f"SELECT COUNT(*), SUM(source_record_count) FROM read_csv("
            f"{sql_quote(final_path.as_posix())}, header=true, columns={duckdb_columns()})"
        ).fetchone()
        if file_check != (daily_rows, source_record_count):
            raise RuntimeError(f"Written-output validation failed for {month}")
    finally:
        connection.close()

    partition.update(
        {
            "status": "complete",
            "output": relative_display(final_path),
            "output_size_bytes": final_path.stat().st_size,
            "daily_rows": daily_rows,
            "minimum_date": str(result[1]),
            "maximum_date": str(result[2]),
            "source_record_count": source_record_count,
            "metric_totals": output_totals,
            "partial_file_count": len(partials),
            "completed_at": utc_now(),
        }
    )
    manifest["updated_at"] = utc_now()
    atomic_write_json(manifest_path, manifest)

    if not config.keep_partials:
        for partial in partials:
            partial.unlink()
        partial_dir.rmdir()
        partition["partials_deleted"] = True
        manifest["updated_at"] = utc_now()
        atomic_write_json(manifest_path, manifest)
    if database_path.exists():
        database_path.unlink()
    shutil.rmtree(temp_dir, ignore_errors=True)


def finalize_manifest(manifest: dict[str, Any], manifest_path: Path) -> None:
    valid_rows, input_totals = aggregate_manifest_inputs(manifest)
    output_source_records = 0
    output_daily_rows = 0
    output_totals = empty_totals()
    for partition in manifest["partitions"].values():
        if partition.get("status") != "complete":
            raise RuntimeError("Cannot finalize: at least one monthly partition is incomplete")
        output_source_records += int(partition["source_record_count"])
        output_daily_rows += int(partition["daily_rows"])
        add_totals(
            output_totals,
            [int(partition["metric_totals"][name]) for name in COUNT_FIELDS],
            Decimal(str(partition["metric_totals"]["total_secs"])),
        )

    checks = {
        "source_record_count_matches_valid_rows": output_source_records == valid_rows,
        **{
            f"{name}_matches": int(output_totals[name]) == int(input_totals[name])
            for name in COUNT_FIELDS
        },
        "total_secs_matches": Decimal(str(output_totals["total_secs"]))
        == Decimal(str(input_totals["total_secs"])),
    }
    if not all(checks.values()):
        raise RuntimeError(f"Final reconciliation failed: {checks}")
    manifest["reconciliation"] = {
        "valid_source_rows": valid_rows,
        "final_source_record_count": output_source_records,
        "final_daily_rows": output_daily_rows,
        "input_metric_totals": input_totals,
        "final_metric_totals": output_totals,
        "checks": checks,
        "total_secs_tolerance": "0 (DECIMAL exact comparison)",
    }
    manifest["status"] = "complete"
    manifest["completed_at"] = utc_now()
    manifest["updated_at"] = utc_now()
    atomic_write_json(manifest_path, manifest)


def run_pipeline(config: PipelineConfig) -> dict[str, Any]:
    if config.chunk_rows <= 0 or config.progress_every <= 0:
        raise ValueError("chunk_rows and progress_every must be greater than zero")
    if config.max_rows is not None and config.max_rows <= 0:
        raise ValueError("max_rows must be greater than zero")
    if not MEMORY_LIMIT_PATTERN.fullmatch(config.duckdb_memory_limit):
        raise ValueError("duckdb_memory_limit must look like 512MB or 2GB")
    for path in config.files:
        if not path.is_file():
            raise FileNotFoundError(path)

    manifest, manifest_path = prepare_run(config)
    try:
        for path in config.files:
            process_source(path, config, manifest, manifest_path)
        for month in sorted(manifest["partitions"]):
            consolidate_partition(month, config, manifest, manifest_path)
        finalize_manifest(manifest, manifest_path)
        print(f"Complete. Manifest: {manifest_path}")
        return manifest
    except KeyboardInterrupt:
        manifest["status"] = "interrupted"
        manifest["updated_at"] = utc_now()
        manifest["failure_type"] = "KeyboardInterrupt"
        atomic_write_json(manifest_path, manifest)
        raise
    except Exception:
        manifest["status"] = "failed"
        manifest["updated_at"] = utc_now()
        manifest["failure_type"] = sys.exc_info()[0].__name__ if sys.exc_info()[0] else "Unknown"
        atomic_write_json(manifest_path, manifest)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create monthly daily-activity aggregates from KKBox user logs."
    )
    parser.add_argument(
        "--files", nargs="+", default=list(SOURCE_NAMES),
        help="Source filenames under data/raw or project-relative/absolute paths.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--chunk-rows", type=int, default=500_000)
    parser.add_argument("--progress-every", type=int, default=100_000)
    parser.add_argument(
        "--max-rows", type=int,
        help="Read at most this many data rows from each selected source (smoke tests).",
    )
    parser.add_argument("--duckdb-memory-limit", default="2GB")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--resume", action="store_true")
    mode.add_argument("--restart", action="store_true")
    parser.add_argument("--keep-partials", action="store_true")
    return parser.parse_args()


def resolve_source(value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate.resolve()
    raw_candidate = RAW_DATA_DIR / candidate
    if len(candidate.parts) == 1 and raw_candidate.exists():
        return raw_candidate.resolve()
    return (PROJECT_ROOT / candidate).resolve()


def main() -> int:
    args = parse_args()
    config = PipelineConfig(
        files=tuple(resolve_source(value) for value in args.files),
        output_dir=(args.output_dir if args.output_dir.is_absolute()
                    else PROJECT_ROOT / args.output_dir).resolve(),
        chunk_rows=args.chunk_rows,
        progress_every=args.progress_every,
        max_rows=args.max_rows,
        duckdb_memory_limit=args.duckdb_memory_limit,
        resume=args.resume,
        restart=args.restart,
        keep_partials=args.keep_partials,
    )
    try:
        run_pipeline(config)
    except KeyboardInterrupt:
        print("Interrupted; completed chunks remain resumable.", file=sys.stderr)
        return 130
    except (OSError, MemoryError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
