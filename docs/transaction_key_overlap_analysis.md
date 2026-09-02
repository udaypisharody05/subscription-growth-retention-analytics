# Transaction Key Overlap Analysis

## Methodology

- transactions_v2.csv was scanned first. Distinct customer, customer+transaction-date, and customer+membership-expiry keys were retained only as SHA-256 digests.
- Each digest used a key-type namespace and eight-byte length-prefixed UTF-8 fields, preventing ambiguous field concatenation.
- transactions.csv was then streamed. Matching v2 digests were removed from the unmatched sets; no original composite-key set or raw row collection was kept.
- A hashed set of distinct original customers was retained solely to calculate the original distinct-user and original-only-user metrics.
- Metrics count distinct logical keys, not row occurrences. Duplicate multiplicity is intentionally ignored.
- No hashes, customer identifiers, or raw transaction records are reported. SHA-256 collision risk is negligible but not eliminated.

## Customer-level overlap

| Metric | Value |
| --- | ---: |
| transactions.csv rows scanned | 21,547,746 |
| transactions_v2.csv rows scanned | 1,431,009 |
| Distinct users in transactions.csv | 2,363,626 |
| Distinct users in transactions_v2.csv | 1,197,050 |
| Users present in both files | 1,134,533 |
| Users only in transactions.csv | 1,229,093 |
| Users only in transactions_v2.csv | 62,517 |
| Percentage of v2 users seen in original | 94.78% |

## Customer + transaction-date overlap

| Metric | Value |
| --- | ---: |
| Distinct v2 keys | 1,397,717 |
| V2 keys found in transactions.csv | 7,249 |
| Overlap percentage | 0.52% |
| Historical distinct v2 keys | 338,868 |
| Historical v2 keys found in original | 7,249 |
| Historical v2 keys not found in original | 331,619 |
| March v2 keys found in original | 0 |

## Customer + membership-expiry overlap

| Metric | Value |
| --- | ---: |
| Distinct v2 keys | 1,424,174 |
| V2 keys found in transactions.csv | 8,650 |
| Overlap percentage | 0.61% |
| V2 keys not found in transactions.csv | 1,415,524 |

## Historical vs March comparison

| V2 transaction-date-key period | Distinct keys | Found in original | Not found in original | Overlap percentage |
| --- | ---: | ---: | ---: | ---: |
| Historical (transaction_date <= 20170228) | 338,868 | 7,249 | 331,619 | 2.14% |
| March 2017 (20170301 through 20170331) | 1,058,849 | 0 | 1,058,849 | 0.00% |

## Conclusion

- 1,134,533 of 1,197,050 distinct v2 customers (94.78%) were also observed in transactions.csv.
- 7,249 of 338,868 distinct historical v2 customer+transaction-date keys (2.14%) were found in transactions.csv.
- These key-level relationships do not prove that records are duplicates, corrections, replacements, or updates.
