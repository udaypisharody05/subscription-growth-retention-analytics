"""Stream immutable KKBox CSV files to create reproducible source fingerprints."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
CACHE_PATH = (
    PROJECT_ROOT / "data" / "processed" / "inspection"
    / "source_file_fingerprints.json"
)
REPORT_PATH = PROJECT_ROOT / "docs" / "source_file_fingerprints.md"
MIB = 1024 * 1024
GIB = 1024 * 1024 * 1024
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

SOURCE_FILES = {
    "members_v3.csv": {
        "relative_path": "data/raw/members_v3.csv",
        "file_size_bytes": 427_921_437,
        "row_count": 6_769_473,
    },
    "train.csv": {
        "relative_path": "data/raw/train.csv",
        "file_size_bytes": 46_667_771,
        "row_count": 992_931,
    },
    "train_v2.csv": {
        "relative_path": "data/raw/train_v2.csv",
        "file_size_bytes": 45_635_134,
        "row_count": 970_960,
    },
    "transactions.csv": {
        "relative_path": "data/raw/transactions.csv",
        "file_size_bytes": 1_729_298_376,
        "row_count": 21_547_746,
    },
    "transactions_v2.csv": {
        "relative_path": "data/raw/transactions_v2.csv",
        "file_size_bytes": 115_394_513,
        "row_count": 1_431_009,
    },
    "user_logs.csv": {
        "relative_path": "data/raw/user_logs.csv",
        "file_size_bytes": 30_514_081_415,
        "row_count": 392_106_543,
    },
    "user_logs_v2.csv": {
        "relative_path": "data/raw/user_logs_v2.csv",
        "file_size_bytes": 1_431_465_728,
        "row_count": 18_396_362,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stream KKBox raw files and record SHA-256 fingerprints."
    )
    parser.add_argument(
        "--files",
        nargs="+",
        choices=tuple(SOURCE_FILES),
        help="Files to fingerprint; default: all seven files.",
    )
    parser.add_argument(
        "--chunk-size-mib",
        type=int,
        default=8,
        help="Binary read size in MiB (default: 8).",
    )
    parser.add_argument(
        "--progress-every-mib",
        type=int,
        default=1024,
        help="Progress interval in MiB (default: 1024).",
    )
    args = parser.parse_args()
    if args.chunk_size_mib <= 0:
        parser.error("--chunk-size-mib must be greater than zero")
    if args.progress_every_mib <= 0:
        parser.error("--progress-every-mib must be greater than zero")
    return args


def iso_modified_time(modified_time_ns: int) -> str:
    """Return a timezone-aware UTC ISO timestamp for filesystem metadata."""
    return datetime.fromtimestamp(
        modified_time_ns / 1_000_000_000, tz=timezone.utc
    ).isoformat().replace("+00:00", "Z")


def load_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {"version": 1, "files": {}}
    with CACHE_PATH.open("r", encoding="utf-8") as cache_file:
        cache = json.load(cache_file)
    if not isinstance(cache, dict) or cache.get("version") != 1:
        raise ValueError(f"Unsupported fingerprint cache format: {CACHE_PATH}")
    if not isinstance(cache.get("files"), dict):
        raise ValueError(f"Invalid fingerprint cache files object: {CACHE_PATH}")
    return cache


def entry_is_current(name: str, entry: Any) -> bool:
    """Validate cached metadata against the known source and its current stat."""
    if not isinstance(entry, dict):
        return False
    expected = SOURCE_FILES[name]
    required_matches = (
        entry.get("file_name") == name,
        entry.get("relative_path") == expected["relative_path"],
        entry.get("file_size_bytes") == expected["file_size_bytes"],
        entry.get("row_count") == expected["row_count"],
        isinstance(entry.get("sha256"), str),
        isinstance(entry.get("file_modified_at_ns"), int),
    )
    if not all(required_matches) or not SHA256_PATTERN.fullmatch(entry["sha256"]):
        return False
    try:
        current_stat = (RAW_DATA_DIR / name).stat()
    except OSError:
        return False
    return (
        current_stat.st_size == expected["file_size_bytes"]
        and current_stat.st_size == entry["file_size_bytes"]
        and current_stat.st_mtime_ns == entry["file_modified_at_ns"]
        and entry.get("file_modified_at")
        == iso_modified_time(current_stat.st_mtime_ns)
    )


def remove_stale_entries(cache: dict[str, Any]) -> bool:
    """Remove unknown or locally stale entries before publishing cache data."""
    retained = {
        name: entry
        for name, entry in cache["files"].items()
        if name in SOURCE_FILES and entry_is_current(name, entry)
    }
    changed = retained != cache["files"]
    cache["files"] = retained
    return changed


def hash_source(
    name: str,
    chunk_size_bytes: int,
    progress_every_bytes: int,
) -> dict[str, Any]:
    expected = SOURCE_FILES[name]
    path = RAW_DATA_DIR / name
    before = path.stat()
    if before.st_size != expected["file_size_bytes"]:
        raise ValueError(
            f"{name}: size mismatch; expected {expected['file_size_bytes']:,} bytes, "
            f"found {before.st_size:,} bytes"
        )

    print(f"Hashing {name}", flush=True)
    digest = hashlib.sha256()
    processed = 0
    next_progress = progress_every_bytes
    with path.open("rb") as source_file:
        while chunk := source_file.read(chunk_size_bytes):
            digest.update(chunk)
            processed += len(chunk)
            if processed >= next_progress:
                print(
                    f"{name}: {processed / GIB:.2f} GiB / "
                    f"{before.st_size / GIB:.2f} GiB processed",
                    flush=True,
                )
                while next_progress <= processed:
                    next_progress += progress_every_bytes

    after = path.stat()
    if processed != expected["file_size_bytes"]:
        raise OSError(
            f"{name}: read {processed:,} bytes; expected "
            f"{expected['file_size_bytes']:,} bytes"
        )
    if after.st_size != before.st_size or after.st_mtime_ns != before.st_mtime_ns:
        raise OSError(f"{name}: file metadata changed while hashing; fingerprint discarded")

    print(f"{name}: fingerprint complete", flush=True)
    return {
        "file_name": name,
        "relative_path": expected["relative_path"],
        "file_size_bytes": expected["file_size_bytes"],
        "row_count": expected["row_count"],
        "sha256": digest.hexdigest(),
        # This is filesystem metadata only, never authoritative source chronology.
        "file_modified_at": iso_modified_time(after.st_mtime_ns),
        # Exact local comparison value; avoids ISO timestamp precision ambiguity.
        "file_modified_at_ns": after.st_mtime_ns,
    }


def build_report(cache: dict[str, Any]) -> str:
    lines = [
        "# KKBox Raw Source Fingerprints",
        "",
        "## Methodology",
        "",
        "- SHA-256 fingerprints are computed by streaming each raw file in bounded "
        "binary chunks; files are never loaded fully into memory.",
        "- Row counts come from earlier verified full streaming scans and are not "
        "recounted by the fingerprint utility.",
        "- Each current file size is checked against its previously verified byte size "
        "before hashing.",
        "- Modification timestamps are filesystem metadata only, not authoritative "
        "source chronology or event timestamps.",
        "- A cached fingerprint is current only while its expected size and exact local "
        "filesystem modification timestamp still match.",
        "- Fingerprints identify the exact local raw-file versions used by this project.",
        "",
        "## Source Files",
        "",
        "| File | Relative path | Size bytes | Verified rows | SHA-256 |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for name in SOURCE_FILES:
        entry = cache["files"].get(name)
        if entry is not None:
            lines.append(
                f"| {entry['file_name']} | {entry['relative_path']} | "
                f"{entry['file_size_bytes']:,} | {entry['row_count']:,} | "
                f"`{entry['sha256']}` |"
            )
    lines.extend([
        "",
        "## Registration Status",
        "",
        "This report records raw-file fingerprints only. PostgreSQL registration "
        "status is documented separately in docs/source_file_registration.md.",
        "",
    ])
    return "\n".join(lines)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(text)
        temporary_path.replace(path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def publish(cache: dict[str, Any]) -> None:
    cache_text = json.dumps(cache, indent=2, sort_keys=True) + "\n"
    atomic_write_text(CACHE_PATH, cache_text)
    atomic_write_text(REPORT_PATH, build_report(cache))


def main() -> int:
    args = parse_args()
    selected = list(dict.fromkeys(args.files or SOURCE_FILES))
    try:
        cache = load_cache()
        if remove_stale_entries(cache):
            publish(cache)

        for name in selected:
            if entry_is_current(name, cache["files"].get(name)):
                print(f"{name}: current cached fingerprint retained", flush=True)
                continue
            entry = hash_source(
                name,
                args.chunk_size_mib * MIB,
                args.progress_every_mib * MIB,
            )
            # Publish only after this file has been hashed and its metadata remained stable.
            cache["files"][name] = entry
            publish(cache)
        # Regenerate the public report even when every selected entry was already current.
        atomic_write_text(REPORT_PATH, build_report(cache))
    except KeyboardInterrupt:
        print(
            "\nFingerprinting interrupted; the current file was not cached.",
            file=sys.stderr,
        )
        return 130
    except (OSError, ValueError, json.JSONDecodeError, MemoryError) as exc:
        print(
            f"Fingerprinting failed ({type(exc).__name__}): {exc}. "
            "The current file was not cached.",
            file=sys.stderr,
        )
        return 1

    print(f"Fingerprint cache: {CACHE_PATH}")
    print(f"Public report: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
