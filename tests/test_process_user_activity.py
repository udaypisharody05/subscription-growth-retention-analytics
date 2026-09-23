from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src" / "ingestion"))

from process_user_activity import (  # noqa: E402
    COUNT_FIELDS,
    EXPECTED_HEADER,
    PipelineConfig,
    run_pipeline,
)
import process_user_activity as activity_pipeline  # noqa: E402


class UserActivityPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.raw = self.root / "raw"
        self.output = self.root / "processed"
        self.raw.mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_source(self, name: str, rows: list[list[object]]) -> Path:
        path = self.raw / name
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(EXPECTED_HEADER)
            writer.writerows(rows)
        return path

    def build_sources(self) -> tuple[Path, Path]:
        historical = self.write_source(
            "user_logs.csv",
            [
                ["u1", "20170101", 1, 2, 3, 4, 5, 6, "1.25"],
                ["u1", "20170101", 10, 10, 10, 10, 10, 10, "2.75"],
                ["u2", "20170102", 2, 0, 0, 0, 0, 0, "0"],
                # Same key as rows 1-2, deliberately placed in another chunk.
                ["u1", "20170101", 100, 100, 100, 100, 100, 100, "0.5"],
                ["u1", "20170201", 1, 1, 1, 1, 1, 1, "3"],
                ["", "20170103", 1, 1, 1, 1, 1, 1, "1"],
                ["u4", "20170230", 1, 1, 1, 1, 1, 1, "1"],
                ["u4", "20170103", "bad", 1, 1, 1, 1, 1, "1"],
                ["u4", "20170103", 1, 1, 1, 1, 1, 1, "not-a-number"],
                ["u4", "20170103", 1, 1],
            ],
        )
        refreshed = self.write_source(
            "user_logs_v2.csv",
            [
                ["u1", "20170301", 1, 1, 1, 1, 1, 1, "1.5"],
                ["u1", "20170301", 2, 2, 2, 2, 2, 2, "2.5"],
                # Suspicious but parseable numeric values are preserved.
                ["u3", "20170302", -1, -1, -1, -1, -1, -1, "-0.25"],
            ],
        )
        return historical, refreshed

    def run_fixture(self, *, resume: bool = False):
        historical = self.raw / "user_logs.csv"
        refreshed = self.raw / "user_logs_v2.csv"
        if not historical.exists():
            historical, refreshed = self.build_sources()
        return run_pipeline(
            PipelineConfig(
                files=(historical, refreshed),
                output_dir=self.output,
                chunk_rows=3,
                progress_every=2,
                duckdb_memory_limit="256MB",
                resume=resume,
            )
        )

    def read_outputs(self) -> dict[tuple[str, str], dict[str, str]]:
        rows: dict[tuple[str, str], dict[str, str]] = {}
        for path in sorted((self.output / "daily").glob("month=*/*.csv")):
            with path.open("r", encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    key = (row["msno"], row["activity_date"])
                    self.assertNotIn(key, rows)
                    rows[key] = row
        return rows

    def test_validation_partitioning_aggregation_and_reconciliation(self) -> None:
        manifest = self.run_fixture()
        rows = self.read_outputs()

        self.assertEqual(manifest["status"], "complete")
        self.assertEqual(set(manifest["partitions"]), {"2017-01", "2017-02", "2017-03"})
        self.assertEqual(len(rows), 5)

        cross_chunk = rows[("u1", "2017-01-01")]
        self.assertEqual(
            [int(cross_chunk[name]) for name in COUNT_FIELDS],
            [111, 112, 113, 114, 115, 116],
        )
        self.assertEqual(Decimal(cross_chunk["total_secs"]), Decimal("4.5"))
        self.assertEqual(int(cross_chunk["source_record_count"]), 3)

        cross_file_period = rows[("u1", "2017-03-01")]
        self.assertEqual([int(cross_file_period[name]) for name in COUNT_FIELDS], [3] * 6)
        self.assertEqual(int(cross_file_period["source_record_count"]), 2)
        self.assertEqual(Decimal(rows[("u3", "2017-03-02")]["total_secs"]), Decimal("-0.25"))

        source_entries = list(manifest["sources"].values())
        self.assertEqual(sum(entry["rows_read"] for entry in source_entries), 13)
        self.assertEqual(sum(entry["valid_rows"] for entry in source_entries), 8)
        self.assertEqual(sum(entry["invalid_rows"] for entry in source_entries), 5)
        historical_reasons = source_entries[0]["invalid_reasons"]
        self.assertEqual(historical_reasons["empty_msno"], 1)
        self.assertEqual(historical_reasons["invalid_date"], 1)
        self.assertEqual(historical_reasons["invalid_num_25"], 1)
        self.assertEqual(historical_reasons["invalid_total_secs"], 1)
        self.assertEqual(historical_reasons["malformed_csv_row"], 1)

        reconciliation = manifest["reconciliation"]
        self.assertEqual(reconciliation["valid_source_rows"], 8)
        self.assertEqual(reconciliation["final_source_record_count"], 8)
        self.assertEqual(reconciliation["final_daily_rows"], 5)
        self.assertTrue(all(reconciliation["checks"].values()))
        self.assertEqual(reconciliation["final_metric_totals"]["num_25"], 116)
        self.assertEqual(reconciliation["final_metric_totals"]["num_unq"], 119)
        self.assertEqual(
            Decimal(reconciliation["final_metric_totals"]["total_secs"]),
            Decimal("11.25"),
        )
        self.assertFalse(any((self.output / "partials").glob("month=*/*.csv")))

    def test_completed_run_can_be_resumed_without_duplicate_output(self) -> None:
        first = self.run_fixture()
        second = self.run_fixture(resume=True)
        self.assertEqual(first["reconciliation"], second["reconciliation"])
        self.assertEqual(len(self.read_outputs()), 5)

    def test_max_rows_is_applied_per_source(self) -> None:
        historical, refreshed = self.build_sources()
        manifest = run_pipeline(
            PipelineConfig(
                files=(historical, refreshed),
                output_dir=self.output,
                chunk_rows=2,
                progress_every=10,
                max_rows=2,
                duckdb_memory_limit="256MB",
            )
        )
        self.assertEqual(
            [entry["rows_read"] for entry in manifest["sources"].values()],
            [2, 2],
        )
        self.assertEqual(manifest["reconciliation"]["valid_source_rows"], 4)
        self.assertEqual(manifest["reconciliation"]["final_source_record_count"], 4)

    def test_chunk_total_decimal_is_serialized_once_per_completed_chunk(self) -> None:
        source = self.write_source(
            "user_logs.csv",
            [
                ["u1", "20170101", 1, 1, 1, 1, 1, 1, "1.25"],
                ["u1", "20170101", 2, 2, 2, 2, 2, 2, "2.75"],
            ],
        )
        config = PipelineConfig(
            files=(source,), output_dir=self.output, chunk_rows=10, progress_every=10
        )
        manifest = activity_pipeline.new_manifest(config)
        manifest_path = self.output / "manifests" / "processing_manifest.json"
        activity_pipeline.atomic_write_json(manifest_path, manifest)

        with patch.object(
            activity_pipeline,
            "decimal_text",
            wraps=activity_pipeline.decimal_text,
        ) as formatter:
            activity_pipeline.process_source(source, config, manifest, manifest_path)

        # Once for the single partial aggregate and once for the chunk manifest
        # total, rather than once for every source row.
        self.assertEqual(formatter.call_count, 2)

    def test_direct_date_validation_accepts_leap_day_and_rejects_bad_day(self) -> None:
        base = {
            "msno": "u1",
            "date": "20160229",
            **{name: "0" for name in COUNT_FIELDS},
            "total_secs": "0",
        }
        parsed = activity_pipeline.parse_activity_row(base)
        self.assertNotIsInstance(parsed, str)
        self.assertEqual(parsed[1], "2016-02-29")

        base["date"] = "20160230"
        self.assertEqual(activity_pipeline.parse_activity_row(base), "invalid_date")

    def test_failed_consolidation_is_marked_failed_and_remains_resumable(self) -> None:
        source = self.write_source(
            "user_logs.csv",
            [["u1", "20170101", 1, 1, 1, 1, 1, 1, "1"]],
        )
        config = PipelineConfig(
            files=(source,), output_dir=self.output, chunk_rows=10, progress_every=10
        )
        with patch.object(
            activity_pipeline,
            "consolidate_partition",
            side_effect=Exception("synthetic engine failure"),
        ):
            with self.assertRaisesRegex(Exception, "synthetic engine failure"):
                run_pipeline(config)

        manifest_path = self.output / "manifests" / "processing_manifest.json"
        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["failure_type"], "Exception")
        self.assertEqual(next(iter(manifest["sources"].values()))["status"], "complete")


if __name__ == "__main__":
    unittest.main()
