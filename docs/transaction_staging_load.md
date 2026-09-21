# Transaction Staging Load

## Scope

This milestone loaded the two registered KKBox transaction source versions into
`staging.transactions`. It did not deduplicate source records, load user logs,
define revenue metrics, or build analytics tables.

## Loading Method

The standard-library loader invokes `psql` with `ON_ERROR_STOP` and uses
PostgreSQL `\copy` into a transaction-local temporary table. PostgreSQL assigns
a 1-based identity to each CSV data row, excluding the header. After validating
the copied row count, required fields, binary flags, dates, and lineage, the
loader inserts typed values into `staging.transactions`. Each source load is
committed atomically only after its complete staged lineage is verified.

Source versions are resolved through the local fingerprint cache and matched to
exactly one `raw.source_file` registration by relative path, byte size, and
SHA-256. Filename alone is not used for lineage resolution. Every staged row
retains the resulting `source_file_key` and its `source_row_number`.

## Row and Lineage Validation

| Source | Source rows | Staged rows | Minimum row number | Maximum row number | Distinct row numbers |
| --- | ---: | ---: | ---: | ---: | ---: |
| `transactions.csv` | 21,547,746 | 21,547,746 | 1 | 21,547,746 | 21,547,746 |
| `transactions_v2.csv` | 1,431,009 | 1,431,009 | 1 | 1,431,009 | 1,431,009 |
| **Combined** | **22,978,755** | **22,978,755** | N/A | N/A | N/A |

The primary lineage key contains no duplicate
`(source_file_key, source_row_number)` pairs. Required typed fields contain no
unexpected NULLs. All generated validation fields are populated, and complete
comparisons against their defining expressions found zero mismatches.

The load left the previously validated state unchanged:

- `raw.source_file`: 7 rows.
- `staging.members`: 6,769,473 rows.
- `staging.churn_labels`: 1,963,891 rows.

## Anomaly and Distribution Validation

The staged results exactly matched the previously verified full-file profile.

| Metric | `transactions.csv` | `transactions_v2.csv` |
| --- | ---: | ---: |
| `is_cancel = false` | 20,690,895 | 1,395,876 |
| `is_cancel = true` | 856,851 | 35,133 |
| Negative expiry delta | 153,660 | 5,106 |
| Zero expiry delta | 471,741 | 17,700 |
| Expiry delta greater than 730 days | 2,344 | 50,121 |
| Paid equals list | 19,832,943 | 1,419,106 |
| Paid below list | 857,381 | 9,639 |
| Paid above list | 857,422 | 2,264 |
| Expiry delta equals plan days | 6,716,387 | 405,903 |
| Expiry shorter than plan days | 3,587,269 | 37,493 |
| Expiry longer than plan days | 11,244,090 | 987,613 |

The calendar-valid but unusual expiry dates were also retained: the original
file contains 1,776 rows expiring on 1970-01-01, and v2 contains one row
expiring on 2036-10-15. The v2 source retains 49 expiry deltas greater than
3,650 days. Zero-valued plan and monetary fields and every documented plan-day
and monetary distribution also matched the verified source profile.

These checks confirm preservation, not business validity. In particular,
`is_cancel` remains distinct from churn, and the greater-than-730-day flag is a
project convention rather than an official invalidity rule.

## Idempotence

A second execution resolved both registered source versions, found each source
complete, skipped both COPY operations, and left `staging.transactions` at
exactly 22,978,755 rows.

## Limitations

The staging load preserves source records and descriptive validation columns.
It does not establish economic deduplication, net revenue, MRR, ARPU, or LTV;
does not interpret payment-method codes; and does not create transaction or
user-activity analytics marts.
