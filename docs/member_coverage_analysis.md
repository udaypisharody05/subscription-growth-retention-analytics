# KKBox Member Coverage Analysis

## Methodology

- The member reference and each source are scanned sequentially. Anonymized msno values are retained only transiently in local memory, with one source set at a time; identifiers are never persisted, printed, or reported.
- Identifier strings are compared directly, without trimming or normalization.
- Empty identifiers are excluded from distinct-user and duplicate-user counts. Empty source rows are counted as rows without member metadata.
- User coverage uses distinct non-empty source users as the denominator. Row coverage uses all source data rows, including empty identifiers.
- Only completed aggregate results are cached. Selected runs preserve unrelated cached results, and interrupted scans do not replace prior results.
- Results describe file snapshots at their recorded completion times. File sizes and modification times guard against changed inputs; they are not content checksums. No identifiers, hashes, or sample records are published.

## members_v3 Integrity

| Metric | Value |
| --- | ---: |
| Total rows | 6,769,473 |
| Distinct non-empty users | 6,769,473 |
| Duplicate occurrences beyond first | 0 |
| Distinct duplicated users | 0 |
| Empty identifiers | 0 |

Reference scan completed: 2026-09-03T04:22:06.988649+00:00

## Coverage Summary

| Source | Rows | Distinct users | Users with member record | Users without member record | User coverage % | Row coverage % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| transactions.csv | 21,547,746 | 2,363,626 | 1,931,003 | 432,623 | 81.6966% | 87.6737% |
| transactions_v2.csv | 1,431,009 | 1,197,050 | 1,077,434 | 119,616 | 90.0074% | 91.0655% |
| train.csv | 992,931 | 992,931 | 877,161 | 115,770 | 88.3406% | 88.3406% |
| train_v2.csv | 970,960 | 970,960 | 860,967 | 109,993 | 88.6717% | 88.6717% |
| user_logs.csv | 392,106,543 | 5,234,111 | 5,063,933 | 170,178 | 96.7487% | 99.5374% |
| user_logs_v2.csv | 18,396,362 | 1,103,894 | 1,103,854 | 40 | 99.9964% | 99.9978% |

## Dataset Details

### transactions.csv

Completed: 2026-09-03T04:05:34.246557+00:00

| Metric | Value |
| --- | ---: |
| Total rows scanned | 21,547,746 |
| Distinct non-empty users | 2,363,626 |
| Users with member metadata | 1,931,003 |
| Users without member metadata | 432,623 |
| User coverage | 81.6966% |
| Rows with member metadata | 18,891,703 |
| Rows without member metadata | 2,656,043 |
| Row coverage | 87.6737% |
| Empty identifier rows | 0 |

### transactions_v2.csv

Completed: 2026-09-03T04:05:43.643234+00:00

| Metric | Value |
| --- | ---: |
| Total rows scanned | 1,431,009 |
| Distinct non-empty users | 1,197,050 |
| Users with member metadata | 1,077,434 |
| Users without member metadata | 119,616 |
| User coverage | 90.0074% |
| Rows with member metadata | 1,303,156 |
| Rows without member metadata | 127,853 |
| Row coverage | 91.0655% |
| Empty identifier rows | 0 |

### train.csv

Completed: 2026-09-03T04:01:44.894232+00:00

| Metric | Value |
| --- | ---: |
| Total rows scanned | 992,931 |
| Distinct non-empty users | 992,931 |
| Users with member metadata | 877,161 |
| Users without member metadata | 115,770 |
| User coverage | 88.3406% |
| Rows with member metadata | 877,161 |
| Rows without member metadata | 115,770 |
| Row coverage | 88.3406% |
| Empty identifier rows | 0 |

### train_v2.csv

Completed: 2026-09-03T04:01:50.746786+00:00

| Metric | Value |
| --- | ---: |
| Total rows scanned | 970,960 |
| Distinct non-empty users | 970,960 |
| Users with member metadata | 860,967 |
| Users without member metadata | 109,993 |
| User coverage | 88.6717% |
| Rows with member metadata | 860,967 |
| Rows without member metadata | 109,993 |
| Row coverage | 88.6717% |
| Empty identifier rows | 0 |

### user_logs.csv

Completed: 2026-09-03T04:29:51.758314+00:00

| Metric | Value |
| --- | ---: |
| Total rows scanned | 392,106,543 |
| Distinct non-empty users | 5,234,111 |
| Users with member metadata | 5,063,933 |
| Users without member metadata | 170,178 |
| User coverage | 96.7487% |
| Rows with member metadata | 390,292,575 |
| Rows without member metadata | 1,813,968 |
| Row coverage | 99.5374% |
| Empty identifier rows | 0 |

### user_logs_v2.csv

Completed: 2026-09-03T04:20:44.018544+00:00

| Metric | Value |
| --- | ---: |
| Total rows scanned | 18,396,362 |
| Distinct non-empty users | 1,103,894 |
| Users with member metadata | 1,103,854 |
| Users without member metadata | 40 |
| User coverage | 99.9964% |
| Rows with member metadata | 18,395,950 |
| Rows without member metadata | 412 |
| Row coverage | 99.9978% |
| Empty identifier rows | 0 |

## Modeling Implications

- transactions.csv: member coverage is incomplete. An inner join to members_v3 would remove 432,623 distinct non-empty source users and 2,656,043 source rows without matching metadata.
- transactions_v2.csv: member coverage is incomplete. An inner join to members_v3 would remove 119,616 distinct non-empty source users and 127,853 source rows without matching metadata.
- train.csv: member coverage is incomplete. An inner join to members_v3 would remove 115,770 distinct non-empty source users and 115,770 source rows without matching metadata.
- train_v2.csv: member coverage is incomplete. An inner join to members_v3 would remove 109,993 distinct non-empty source users and 109,993 source rows without matching metadata.
- user_logs.csv: member coverage is incomplete. An inner join to members_v3 would remove 170,178 distinct non-empty source users and 1,813,968 source rows without matching metadata.
- user_logs_v2.csv: member coverage is incomplete. An inner join to members_v3 would remove 40 distinct non-empty source users and 412 source rows without matching metadata.

members_v3 does not provide complete customer coverage across the transaction, churn-label, and activity sources; using it as the mandatory side of an inner join would exclude valid source records.

No final modeling decision is made and no SQL tables are created.
