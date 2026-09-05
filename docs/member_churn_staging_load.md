# Member and Churn Staging Load

## Sources

| Source | Destination | Source rows | Staged rows | Cohort |
| --- | --- | ---: | ---: | --- |
| members_v3.csv | staging.members | 6,769,473 | 6,769,473 | N/A |
| train.csv | staging.churn_labels | 992,931 | 992,931 | 2017-02-01 |
| train_v2.csv | staging.churn_labels | 970,960 | 970,960 | 2017-03-01 |

The three files were loaded with PostgreSQL `\copy` through transaction-local text tables. Source values and row counts were validated before typed insertion, and each source load committed as an independent transaction.

## Lineage

`source_file_key` resolves the exact `raw.source_file` version by repository-relative path, byte size, and SHA-256—not by filename alone. `source_row_number` is the deterministic, 1-based CSV data-row position assigned during ordered COPY processing; the header is excluded.

The raw CSV files remain immutable on disk. Every staged record retains its file-level and row-level lineage through the composite primary key `(source_file_key, source_row_number)`.

## Member Load Validation

- Rows: 6,769,473
- Distinct `source_row_number`: 6,769,473; range 1 through 6,769,473
- Distinct non-empty `msno`: 6,769,473; empty identifiers: 0
- NULL required fields: 0
- Empty source gender values became SQL NULL; verified NULL gender rows: 4,429,505
- Source `bd` values were preserved in `bd_raw`: 4,540,215 rows equal 0, 274 rows are negative, and 5,377 rows exceed 100
- No age field, city-name interpretation, or registered-via interpretation was introduced

## Churn Load Validation

| Source | Rows | FALSE | TRUE | Cohort date |
| --- | ---: | ---: | ---: | --- |
| train.csv | 992,931 | 929,460 | 63,471 | 2017-02-01 |
| train_v2.csv | 970,960 | 883,630 | 87,330 | 2017-03-01 |

Each source has one distinct non-empty `msno` and one distinct source-row number per row. Both source-row ranges begin at 1 and end at their verified row counts. No NULL churn labels were loaded.

The cohort dates are expiry-cohort month anchors, not exact churn dates. The load preserves churn as a time-dependent observation and does not equate it with transaction cancellation.

| User relationship / transition | Users |
| --- | ---: |
| Shared users | 881,701 |
| Only train.csv | 111,230 |
| Only train_v2.csv | 89,259 |
| FALSE -> FALSE | 824,659 |
| FALSE -> TRUE | 40,721 |
| TRUE -> FALSE | 5,269 |
| TRUE -> TRUE | 11,052 |

These exact cross-checks match the previously profiled label semantics. No observations were transformed or deduplicated based on the transitions.

## Member Coverage

| Churn source | With member metadata | Without member metadata |
| --- | ---: | ---: |
| train.csv | 877,161 | 115,770 |
| train_v2.csv | 860,967 | 109,993 |

Member data is optional enrichment rather than the customer universe. Downstream analytics must use LEFT JOIN semantics when enriching churn or customer observations so valid users without member metadata are not discarded.

## Idempotence

The loader was executed a second time against the same registered source versions. It validated complete row counts and contiguous, distinct lineage ranges, recognized all three sources as already completely loaded, skipped COPY and insertion, and left the totals unchanged.

## Scope

- `staging.members` now contains 6,769,473 member source rows.
- `staging.churn_labels` now contains 1,963,891 time-dependent label observations.
- Transactions are not loaded; `staging.transactions` remains empty.
- User activity is not loaded, and no full user-log staging table exists.
- Analytics dimensions and facts have not been created.
