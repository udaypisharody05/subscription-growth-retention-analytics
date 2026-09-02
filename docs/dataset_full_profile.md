# KKBox Dataset Full Profile

> These verified results were obtained from completed sequential, memory-bounded scans of all seven raw CSV files. This combined report uses the manually verified results without rescanning the datasets. It contains no raw customer records or user IDs.

## Summary

| Filename | Exact rows | Malformed CSV rows | Minimum date(s) | Maximum date(s) | Invalid date count(s) |
| --- | ---: | ---: | --- | --- | --- |
| members_v3.csv | 6,769,473 | 0 | registration_init_time: 20040326 | registration_init_time: 20170429 | registration_init_time: 0 |
| train.csv | 992,931 | 0 | N/A | N/A | N/A |
| train_v2.csv | 970,960 | 0 | N/A | N/A | N/A |
| transactions.csv | 21,547,746 | 0 | transaction_date: 20150101<br>membership_expire_date: 19700101 | transaction_date: 20170228<br>membership_expire_date: 20170331 | transaction_date: 0<br>membership_expire_date: 0 |
| transactions_v2.csv | 1,431,009 | 0 | transaction_date: 20150101<br>membership_expire_date: 20160419 | transaction_date: 20170331<br>membership_expire_date: 20361015 | transaction_date: 0<br>membership_expire_date: 0 |
| user_logs.csv | 392,106,543 | 0 | date: 20150101 | date: 20170228 | date: 0 |
| user_logs_v2.csv | 18,396,362 | 0 | date: 20170301 | date: 20170331 | date: 0 |

## members_v3.csv

- Exact data-row count: 6,769,473
- Malformed CSV row count: 0

| Date column | Minimum valid date | Maximum valid date | Invalid non-empty values |
| --- | --- | --- | ---: |
| registration_init_time | 20040326 | 20170429 | 0 |

## train.csv

- Exact data-row count: 992,931
- Malformed CSV row count: 0

No date columns were profiled for this dataset. Date coverage: N/A.

## train_v2.csv

- Exact data-row count: 970,960
- Malformed CSV row count: 0

No date columns were profiled for this dataset. Date coverage: N/A.

## transactions.csv

- Exact data-row count: 21,547,746
- Malformed CSV row count: 0

| Date column | Minimum valid date | Maximum valid date | Invalid non-empty values |
| --- | --- | --- | ---: |
| transaction_date | 20150101 | 20170228 | 0 |
| membership_expire_date | 19700101 | 20170331 | 0 |

## transactions_v2.csv

- Exact data-row count: 1,431,009
- Malformed CSV row count: 0

| Date column | Minimum valid date | Maximum valid date | Invalid non-empty values |
| --- | --- | --- | ---: |
| transaction_date | 20150101 | 20170331 | 0 |
| membership_expire_date | 20160419 | 20361015 | 0 |

## user_logs.csv

- Exact data-row count: 392,106,543
- Malformed CSV row count: 0

| Date column | Minimum valid date | Maximum valid date | Invalid non-empty values |
| --- | --- | --- | ---: |
| date | 20150101 | 20170228 | 0 |

## user_logs_v2.csv

- Exact data-row count: 18,396,362
- Malformed CSV row count: 0

| Date column | Minimum valid date | Maximum valid date | Invalid non-empty values |
| --- | --- | --- | ---: |
| date | 20170301 | 20170331 | 0 |

## Initial observations

- user_logs.csv and user_logs_v2.csv have non-overlapping date ranges, with v2 covering March 2017.
- transactions_v2.csv overlaps the historical transaction_date range of transactions.csv, so the files must not be blindly concatenated without overlap analysis.
- membership_expire_date contains structurally valid but suspicious extremes such as 19700101 and 20361015; these require later data-quality investigation.
