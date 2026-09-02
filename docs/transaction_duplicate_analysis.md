# Transaction Duplicate Analysis

## Methodology

- Both files were scanned sequentially to completion, with v2 scanned first.
- All nine columns were compared in a fixed order as parsed CSV strings. No trimming, type coercion, cleaning, or date normalization was applied.
- Each field was encoded as its eight-byte big-endian UTF-8 byte length followed by its UTF-8 bytes, then the complete record was hashed with SHA-256.
- Hash equality is treated as full-row equality. SHA-256 collision risk is negligible but not eliminated; raw-row collision verification was not performed.
- Only v2 digests and occurrence/match state were retained. The original file was streamed without retaining its rows.
- Shared occurrences for a row equal the smaller of its two file counts. Distinct shared rows are counted once regardless of multiplicity.
- Period percentages use the total v2 occurrences in that period; the overall percentage uses all v2 occurrences. No identifiers, digests, or records are output.

## Overall exact-overlap summary

| Metric | Value |
| --- | ---: |
| Original file rows scanned | 21,547,746 |
| Total v2 rows | 1,431,009 |
| Distinct v2 full rows | 1,431,009 |
| Duplicate occurrences within v2 (beyond the first) | 0 |
| Distinct exact rows shared with original | 0 |
| Exact v2 occurrences represented in original (multiplicity-aware) | 0 |
| Exact overlap percentage | 0.00% |
| V2 occurrences not represented exactly | 1,431,009 |

## Historical period (transaction_date <= 20170228)

| Metric | Value |
| --- | ---: |
| Total v2 rows | 361,187 |
| Distinct v2 full rows | 361,187 |
| Distinct exact rows shared | 0 |
| Exact matched occurrences | 0 |
| Exact match percentage | 0.00% |
| Occurrences not exactly matched | 361,187 |

## March 2017 (20170301 through 20170331)

| Metric | Value |
| --- | ---: |
| Total v2 rows | 1,069,822 |
| Distinct v2 full rows | 1,069,822 |
| Distinct exact rows shared | 0 |
| Exact matched occurrences | 0 |
| Exact match percentage | 0.00% |
| Occurrences not exactly matched | 1,069,822 |

## Duplicates within transactions_v2.csv

- Distinct full rows occurring more than once: 0.
- Duplicate occurrences beyond each row's first occurrence: 0.
- A row appearing three times contributes two duplicate occurrences.

## Conclusion

Under the SHA-256 comparison described above, 0 distinct full rows are shared, representing 0 matched occurrences (0.00% of v2). 1,431,009 v2 occurrences remain unmatched after respecting multiplicity. These counts do not establish why unmatched records exist or whether they are corrections or new transactions.
