# PostgreSQL Source File Registration

## Database Target

- Database: `subscription_growth_retention`
- Host: `localhost`
- PostgreSQL version: 18.6

No credentials or credential locations are recorded in this document.

## Registered Source Versions

| File | Relative path | Size bytes | Verified rows | SHA-256 |
| --- | --- | ---: | ---: | --- |
| members_v3.csv | data/raw/members_v3.csv | 427,921,437 | 6,769,473 | `5bacf7d28ee97b7f017feca8650f84169cfcd97bad8995e81344c41e31989edd` |
| train.csv | data/raw/train.csv | 46,667,771 | 992,931 | `14140a13139b9952686a85b70378c106da4cef43180a3cd50a2962ce64724767` |
| train_v2.csv | data/raw/train_v2.csv | 45,635,134 | 970,960 | `1f7590a3467174f5a147db3fb85dd1393074b6c13da0fd6e70af31bf37dee5cc` |
| transactions.csv | data/raw/transactions.csv | 1,729,298,376 | 21,547,746 | `537c269140742fc74b28ba83941dff7b0ca00974dd48b80994948b8917adddef` |
| transactions_v2.csv | data/raw/transactions_v2.csv | 115,394,513 | 1,431,009 | `1d3015e32ed1661e9cfe813a9779b1b33e9d1d0829f1203633440045d4c6ea36` |
| user_logs.csv | data/raw/user_logs.csv | 30,514,081,415 | 392,106,543 | `32d83038c86f7974b8f346bb7da1876a186248aa42c74a432517e70cf514d729` |
| user_logs_v2.csv | data/raw/user_logs_v2.csv | 1,431,465,728 | 18,396,362 | `0188c4111de1c4fa4dc3fb6253542f14e142e4d05bbf2f3a4c1c345f0014bdce` |

## Verification Results

- The version 1 fingerprint cache was validated against the seven-file allowlist, expected paths, verified sizes and row counts, lowercase SHA-256 format, timezone-aware modification timestamps, and integer nanosecond timestamps.
- All raw files still match their cached byte sizes and exact filesystem modification timestamps. No rehashing or row recounting was needed.
- The manifest contained 0 rows and 0 expected fingerprint matches before this registration.
- The registration completed in an explicit transaction and committed successfully.
- Seven expected source versions were registered and independently verified against file name, relative path, size, row count, SHA-256, and filesystem modification timestamp.
- Exactly one manifest row exists for each expected fingerprint.
- A second identical execution inserted 0 rows; total manifest rows remained 7, proving this registration was idempotent.
- No duplicate identical source versions or NULL-hash registrations were created for these files.
- No absolute filesystem paths were stored, and no unexpected manifest rows were created by this milestone.
- Raw files were not modified.

## Lineage Notes

`raw.source_file` is a file-level provenance manifest. It registers metadata for immutable source-file versions; it does not contain the raw CSV records, which remain on disk under `data/raw/`.

`file_modified_at` records filesystem metadata and is not authoritative source chronology or an event timestamp. SHA-256 identifies the exact registered local raw-file version. `source_file_key` is a generated surrogate lineage key and does not imply source chronology.
