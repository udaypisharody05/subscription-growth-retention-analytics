# User Activity Preprocessing Pipeline

## Purpose and scope

`src/ingestion/process_user_activity.py` converts the two immutable KKBox
activity files into daily aggregates at the grain `msno + activity_date`. It is
designed for the approximately 410 million source records without loading a
whole source file, all users, or all daily keys into Python memory.

This milestone creates local, PostgreSQL-ready CSV partitions only. It does not
load user logs or aggregates into PostgreSQL, alter the current analytics layer,
or define engagement/churn conclusions.

## Architecture

1. Python's standard `csv` reader consumes a configurable number of rows at a
   time (500,000 by default).
2. Each row is validated for a non-empty `msno`, a real `YYYYMMDD` date, six
   signed integer count fields, and a finite decimal `total_secs` value.
3. Valid rows are aggregated within the chunk by `msno + activity_date`.
   Counts, `total_secs`, and `source_record_count` are summed independently.
4. Each chunk writes atomic monthly partial CSVs under
   `data/processed/user_activity/partials/month=YYYY-MM/`.
5. DuckDB consolidates one month at a time in a disk-backed work database. This
   second aggregation merges keys repeated in different chunks or source files.
6. Validated final CSVs are atomically published under
   `data/processed/user_activity/daily/month=YYYY-MM/`. Monthly partials are
   removed only after their final output and reconciliation metadata are saved.
7. An atomic JSON manifest at
   `data/processed/user_activity/manifests/processing_manifest.json` records
   source file size/mtime, progress, invalid-row reasons, date coverage, input
   totals, final partition totals, and reconciliation checks. It contains no
   customer identifiers or raw records.

DuckDB is a local processing dependency, not a replacement for PostgreSQL as
the project warehouse. Its disk spilling and grouped scans make cross-chunk
consolidation safe without a massive process-wide Python dictionary.
Production consolidation uses one DuckDB thread and disables insertion-order
preservation so large monthly hash aggregates can stay within the configured
memory cap. Failed month databases/spill files are cleared on resume; the
validated monthly partials remain the authoritative consolidation input.

## Output schema

| Field | Treatment |
| --- | --- |
| `msno`, `activity_date` | Final daily key; date is emitted as `YYYY-MM-DD` |
| `num_25` through `num_100` | Independently summed source counts |
| `num_unq` | Summed source metric; not claimed as true daily distinct songs |
| `total_secs` | Exact decimal sum using `DECIMAL(38,12)` during consolidation |
| `source_record_count` | Number of valid source records contributing to the daily row |

Parseable unusual values, including negative numbers, are preserved. Invalid
rows are counted by reason and excluded; no row contents or identifiers are
written to the manifest.

## Reconciliation

The run is marked complete only when all of these hold across every final
partition:

- `SUM(source_record_count) = valid source rows processed`;
- final sums equal input sums for all six count metrics;
- the final `total_secs` sum equals the input sum.

The implementation uses exact decimal arithmetic with scale 12, so the current
documented `total_secs` tolerance is zero. Inputs exceeding that explicit
decimal range are counted as invalid rather than silently rounded.

## Running safely

Install the declared dependencies, then use a small smoke run first:

```powershell
python src/ingestion/process_user_activity.py `
  --files user_logs.csv user_logs_v2.csv `
  --max-rows 100000 `
  --output-dir data/processed/user_activity_smoke `
  --restart
```

`--max-rows` applies separately to each selected source. Use `--chunk-rows` to
bound the Python aggregation dictionary and `--duckdb-memory-limit` to cap the
consolidation engine. Progress is printed every 100,000 input rows by default.

For an interrupted run, rerun the identical command with `--resume` instead of
`--restart`. Resume requires unchanged source size/mtime and identical material
configuration. Atomic partial and manifest writes prevent a current chunk from
being recorded as complete before its files exist. Use `--restart` to discard
only the explicitly selected output directory and begin again.

The production run uses the dedicated ignored location
`data/processed/user_activity/`. A future rerun must be scheduled deliberately
with adequate temporary disk space; tests never initiate a full source scan.

`--restart` removes only the pipeline-owned `partials`, `daily`, `work`, and
`manifests` children of the selected output directory. It does not recursively
delete the output directory itself or unrelated files stored there.

## Bounded real-data smoke test

The implementation was exercised on the first 100,000 rows of each real source
(200,000 source rows total) using 25,000-row chunks and a 512 MB DuckDB memory
limit. This was a bounded validation run, not a complete-dataset result.

| Measure | Smoke result |
| --- | ---: |
| Rows read | 200,000 |
| Valid rows | 200,000 |
| Invalid rows | 0 |
| Monthly partitions | 27 |
| Final daily rows | 200,000 |
| Final `source_record_count` | 200,000 |
| `num_25` sum | 1,267,952 |
| `num_50` sum | 315,480 |
| `num_75` sum | 195,219 |
| `num_985` sum | 223,243 |
| `num_100` sum | 6,145,766 |
| `num_unq` sum | 5,940,346 |
| `total_secs` sum | -184,467,439,121,488,766.408 |

Every input/output metric check passed exactly, including
`SUM(source_record_count) = 200,000`. The extreme negative `total_secs` total is
an observed consequence of unusual parseable values in this bounded slice; the
pipeline intentionally preserved it rather than silently correcting or deleting
it. It is not presented as a business metric or a full-source distribution.

## Full production run

The completed production run used 250,000-row Python chunks, a 2 GB DuckDB
memory cap, one DuckDB consolidation thread, and disk spill under the ignored
processed-data directory. Both raw sources were read completely; no PostgreSQL
or Power BI object was changed.

| Source | Rows read | Valid | Invalid | Date coverage |
| --- | ---: | ---: | ---: | --- |
| `user_logs.csv` | 392,106,543 | 392,106,543 | 0 | 2015-01-01 to 2017-02-28 |
| `user_logs_v2.csv` | 18,396,362 | 18,396,362 | 0 | 2017-03-01 to 2017-03-31 |
| **Total** | **410,502,905** | **410,502,905** | **0** | 2015-01-01 to 2017-03-31 |

The final output contains 410,502,905 daily keys in 27 monthly partitions and
has a total `source_record_count` of 410,502,905. Therefore zero source records
were collapsed for these files: the implemented aggregation does not assume
source uniqueness, but the complete inputs empirically contained one valid
record per final `msno + activity_date` key. No month spans both files because
their verified date ranges do not overlap; March 2017 comes only from
`user_logs_v2.csv`.

| Metric | Exact reconciled total |
| --- | ---: |
| `num_25` | 2,667,401,131 |
| `num_50` | 670,926,016 |
| `num_75` | 416,120,787 |
| `num_985` | 462,424,161 |
| `num_100` | 12,602,900,726 |
| `num_unq` | 12,332,706,347 |
| `total_secs` | -566,534,213,710,238,639,355.8785 |

All seven input/output metric checks and the `source_record_count` check passed
exactly with zero decimal tolerance. The extreme negative `total_secs` total is
an observed source-quality characteristic caused by parseable negative values.
Those values were preserved; the result is not treated as a valid business KPI.
There were no rejected rows or invalid-row reasons.

### Final monthly daily-key counts

| Month | Daily rows | Month | Daily rows | Month | Daily rows |
| --- | ---: | --- | ---: | --- | ---: |
| 2015-01 | 12,897,706 | 2015-10 | 14,403,123 | 2016-07 | 16,694,873 |
| 2015-02 | 11,457,186 | 2015-11 | 14,370,471 | 2016-08 | 16,839,510 |
| 2015-03 | 13,233,548 | 2015-12 | 15,043,579 | 2016-09 | 16,473,693 |
| 2015-04 | 13,146,949 | 2016-01 | 15,117,586 | 2016-10 | 17,557,264 |
| 2015-05 | 13,477,134 | 2016-02 | 13,936,796 | 2016-11 | 17,487,012 |
| 2015-06 | 13,111,785 | 2016-03 | 15,998,873 | 2016-12 | 18,108,364 |
| 2015-07 | 13,186,484 | 2016-04 | 15,883,383 | 2017-01 | 17,908,094 |
| 2015-08 | 13,428,113 | 2016-05 | 16,524,642 | 2017-02 | 16,079,619 |
| 2015-09 | 13,559,390 | 2016-06 | 16,181,366 | 2017-03 | 18,396,362 |

### Production-scale fixes

Two narrow fixes were required during the run. Per-row serialization of the
chunk-level Decimal total was replaced by an in-memory Decimal accumulator, and
date validation now uses direct numeric calendar components rather than
`strptime`; unsorted partial writes avoid ordering work that DuckDB performs at
the final boundary. When the first full monthly hash aggregate reached the 2 GB
cap, consolidation was set to one thread with insertion-order preservation
disabled, following DuckDB's bounded-memory guidance. Failed month spill files
are removed before retry, while validated partial inputs remain intact. The
sources resumed from their last atomic checkpoints and were not restarted.

## Tests

`python -m unittest discover -s tests -v` uses synthetic CSVs and covers:

- duplicate user/date rows within one chunk and across chunk boundaries;
- aggregation across source files and multiple monthly partitions;
- empty identifiers, invalid dates, invalid numerics, and malformed rows;
- preservation of unusual but parseable numeric values;
- all metric and `source_record_count` reconciliations;
- cleanup of validated partials, bounded `--max-rows`, and safe completed-run
  resume behavior;
- calendar validation, efficient chunk-total serialization, and failure-state
  preservation for resumable consolidation.

All generated test and smoke artifacts are under ignored temporary or
`data/processed/` paths and must not be committed.
