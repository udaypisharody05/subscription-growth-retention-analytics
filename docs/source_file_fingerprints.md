# KKBox Raw Source Fingerprints

## Methodology

- SHA-256 fingerprints are computed by streaming each raw file in bounded binary chunks; files are never loaded fully into memory.
- Row counts come from earlier verified full streaming scans and are not recounted by the fingerprint utility.
- Each current file size is checked against its previously verified byte size before hashing.
- Modification timestamps are filesystem metadata only, not authoritative source chronology or event timestamps.
- A cached fingerprint is current only while its expected size and exact local filesystem modification timestamp still match.
- Fingerprints identify the exact local raw-file versions used by this project.

## Source Files

| File | Relative path | Size bytes | Verified rows | SHA-256 |
| --- | --- | ---: | ---: | --- |
| members_v3.csv | data/raw/members_v3.csv | 427,921,437 | 6,769,473 | `5bacf7d28ee97b7f017feca8650f84169cfcd97bad8995e81344c41e31989edd` |
| train.csv | data/raw/train.csv | 46,667,771 | 992,931 | `14140a13139b9952686a85b70378c106da4cef43180a3cd50a2962ce64724767` |
| train_v2.csv | data/raw/train_v2.csv | 45,635,134 | 970,960 | `1f7590a3467174f5a147db3fb85dd1393074b6c13da0fd6e70af31bf37dee5cc` |
| transactions.csv | data/raw/transactions.csv | 1,729,298,376 | 21,547,746 | `537c269140742fc74b28ba83941dff7b0ca00974dd48b80994948b8917adddef` |
| transactions_v2.csv | data/raw/transactions_v2.csv | 115,394,513 | 1,431,009 | `1d3015e32ed1661e9cfe813a9779b1b33e9d1d0829f1203633440045d4c6ea36` |
| user_logs.csv | data/raw/user_logs.csv | 30,514,081,415 | 392,106,543 | `32d83038c86f7974b8f346bb7da1876a186248aa42c74a432517e70cf514d729` |
| user_logs_v2.csv | data/raw/user_logs_v2.csv | 1,431,465,728 | 18,396,362 | `0188c4111de1c4fa4dc3fb6253542f14e142e4d05bbf2f3a4c1c345f0014bdce` |

## Registration Status

This report records raw-file fingerprints only. PostgreSQL registration status is documented separately in docs/source_file_registration.md.
