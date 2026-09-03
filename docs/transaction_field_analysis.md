# KKBox Transaction Field Analysis

## Methodology

Completed sources: transactions.csv, transactions_v2.csv.
Unscanned sources: none.

- Files were scanned sequentially and kept separate. Exact column order and field counts were validated; no source rows were cleaned, deleted, or deduplicated.
- Integer syntax is an optional single sign followed by ASCII digits. Empty fields are counted separately; decimals, whitespace-padded values, and malformed strings are not coerced. Frequencies and relationships use parsed integers.
- Binary validity means a parsed integer equal to 0 or 1. Original flag strings are also frequency-counted, so alternative textual representations remain visible.
- Dates require eight ASCII digits and full calendar validity. Bounded parser caches avoid repeatedly parsing common field values; they retain no customer IDs.
- Numeric quantiles use exact frequency-weighted linear interpolation at zero-based position (N - 1) * p. Empty/non-integer values are excluded; date-delta quantiles require two valid dates. No row-sized arrays or sampling are used.
- Cross-field checks include only rows with the required valid inputs. Monetary/flag summary failures count a row once even if both fields fail. Date invalid counts exclude empty fields, which are shown separately.
- Threshold counts overlap. Negative/high values are inspection flags, not automatic invalidity judgments. Source code meanings and currency units are not inferred.
- No identifiers, hashes, raw records, or sample customer records are reported.

## Source Summary

| Metric | transactions.csv | transactions_v2.csv |
| --- | ---: | ---: |
| Rows | 21,547,746 | 1,431,009 |
| Invalid payment_plan_days (empty/non-integer) | 0 | 0 |
| Invalid monetary rows (either field empty/non-integer) | 0 | 0 |
| Invalid flag rows (either field empty/non-binary) | 0 | 0 |
| Invalid non-empty transaction dates | 0 | 0 |
| Empty transaction dates | 0 | 0 |
| Invalid non-empty expiry dates | 0 | 0 |
| Empty expiry dates | 0 | 0 |
| Negative expiry deltas | 153,660 | 5,106 |
| Actual paid < list price | 857,381 | 9,639 |
| Actual paid > list price | 857,422 | 2,264 |

### Integer field parsing

| Source | Field | Empty | Non-integer | Numeric rows | Distinct numeric | Min | Max |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| transactions.csv | payment_method_id | 0 | 0 | 21,547,746 | 40 | 1 | 41 |
| transactions.csv | payment_plan_days | 0 | 0 | 21,547,746 | 37 | 0 | 450 |
| transactions.csv | plan_list_price | 0 | 0 | 21,547,746 | 51 | 0 | 2,000 |
| transactions.csv | actual_amount_paid | 0 | 0 | 21,547,746 | 57 | 0 | 2,000 |
| transactions.csv | is_auto_renew | 0 | 0 | 21,547,746 | 2 | 0 | 1 |
| transactions.csv | is_cancel | 0 | 0 | 21,547,746 | 2 | 0 | 1 |
| transactions_v2.csv | payment_method_id | 0 | 0 | 1,431,009 | 37 | 2 | 41 |
| transactions_v2.csv | payment_plan_days | 0 | 0 | 1,431,009 | 31 | 0 | 450 |
| transactions_v2.csv | plan_list_price | 0 | 0 | 1,431,009 | 48 | 0 | 2,000 |
| transactions_v2.csv | actual_amount_paid | 0 | 0 | 1,431,009 | 53 | 0 | 2,000 |
| transactions_v2.csv | is_auto_renew | 0 | 0 | 1,431,009 | 2 | 0 | 1 |
| transactions_v2.csv | is_cancel | 0 | 0 | 1,431,009 | 2 | 0 | 1 |

## payment_method_id

### transactions.csv

| Metric | Value |
| --- | ---: |
| Numeric rows | 21,547,746 |
| Minimum | 1 |
| Maximum | 41 |
| Rows < 0 | 0 |
| Rows = 0 | 0 |
| Rows > 0 | 21,547,746 |

| Numeric source value | Rows |
| --- | ---: |
| 41 | 11,526,454 |
| 40 | 2,225,283 |
| 38 | 1,703,590 |
| 39 | 1,466,655 |
| 37 | 1,007,689 |
| 36 | 855,115 |
| 34 | 731,539 |
| 35 | 541,399 |
| 33 | 411,164 |
| 31 | 252,342 |
| 30 | 160,957 |
| 32 | 146,481 |
| 29 | 113,885 |
| 28 | 95,733 |
| 27 | 62,525 |
| 23 | 42,386 |
| 19 | 32,073 |
| 20 | 28,278 |
| 21 | 22,883 |
| 22 | 20,130 |
| 24 | 16,196 |
| 18 | 16,177 |
| 25 | 13,780 |
| 14 | 13,621 |
| 16 | 11,064 |
| 17 | 7,437 |
| 13 | 6,571 |
| 26 | 4,591 |
| 12 | 3,834 |
| 11 | 2,129 |
| 15 | 1,479 |
| 10 | 1,326 |
| 7 | 1,094 |
| 8 | 657 |
| 5 | 474 |
| 6 | 466 |
| 3 | 210 |
| 2 | 52 |
| 4 | 15 |
| 1 | 12 |

### transactions_v2.csv

| Metric | Value |
| --- | ---: |
| Numeric rows | 1,431,009 |
| Minimum | 2 |
| Maximum | 41 |
| Rows < 0 | 0 |
| Rows = 0 | 0 |
| Rows > 0 | 1,431,009 |

| Numeric source value | Rows |
| --- | ---: |
| 41 | 696,696 |
| 39 | 137,120 |
| 38 | 115,875 |
| 32 | 100,982 |
| 36 | 90,844 |
| 40 | 82,747 |
| 37 | 40,414 |
| 34 | 31,099 |
| 29 | 24,957 |
| 30 | 21,182 |
| 33 | 16,715 |
| 31 | 11,597 |
| 35 | 9,759 |
| 22 | 9,563 |
| 15 | 7,705 |
| 20 | 6,651 |
| 13 | 5,050 |
| 28 | 3,452 |
| 12 | 2,858 |
| 23 | 2,719 |
| 17 | 2,532 |
| 19 | 2,136 |
| 27 | 2,074 |
| 21 | 1,846 |
| 16 | 1,842 |
| 18 | 714 |
| 14 | 672 |
| 26 | 668 |
| 6 | 186 |
| 8 | 179 |
| 11 | 79 |
| 3 | 42 |
| 10 | 40 |
| 25 | 5 |
| 24 | 4 |
| 2 | 4 |
| 5 | 1 |


## payment_plan_days

### transactions.csv

| Metric | Value |
| --- | ---: |
| Numeric rows | 21,547,746 |
| Minimum | 0 |
| Maximum | 450 |
| Rows < 0 | 0 |
| Rows = 0 | 870,124 |
| Rows > 0 | 20,677,622 |
| Rows > 31 | 326,729 |
| Rows > 365 | 94,058 |
| Rows > 730 | 0 |

Quantiles over numeric rows:

| Metric | Value |
| --- | ---: |
| p01 | 0 |
| p05 | 7 |
| p25 | 30 |
| median | 30 |
| p75 | 30 |
| p95 | 31 |
| p99 | 195 |

| Numeric source value | Rows |
| --- | ---: |
| 30 | 18,956,290 |
| 0 | 870,124 |
| 31 | 766,608 |
| 7 | 577,639 |
| 195 | 110,234 |
| 410 | 80,139 |
| 180 | 52,272 |
| 10 | 38,216 |
| 100 | 24,154 |
| 90 | 12,310 |
| 395 | 10,790 |
| 120 | 10,007 |
| 60 | 7,167 |
| 14 | 6,365 |
| 200 | 5,838 |
| 360 | 5,486 |
| 1 | 4,759 |
| 400 | 1,856 |
| 450 | 1,271 |
| 240 | 1,088 |

Top 20 of 37 distinct numeric values shown; all frequencies were calculated.

### transactions_v2.csv

| Metric | Value |
| --- | ---: |
| Numeric rows | 1,431,009 |
| Minimum | 0 |
| Maximum | 450 |
| Rows < 0 | 0 |
| Rows = 0 | 2,218 |
| Rows > 0 | 1,428,791 |
| Rows > 31 | 197,427 |
| Rows > 365 | 98,727 |
| Rows > 730 | 0 |

Quantiles over numeric rows:

| Metric | Value |
| --- | ---: |
| p01 | 7 |
| p05 | 30 |
| p25 | 30 |
| median | 30 |
| p75 | 30 |
| p95 | 410 |
| p99 | 410 |

| Numeric source value | Rows |
| --- | ---: |
| 30 | 1,217,998 |
| 410 | 82,097 |
| 195 | 28,568 |
| 180 | 23,900 |
| 90 | 19,130 |
| 7 | 12,168 |
| 395 | 9,753 |
| 360 | 4,658 |
| 100 | 4,098 |
| 365 | 3,838 |
| 120 | 3,612 |
| 240 | 3,440 |
| 415 | 3,298 |
| 60 | 3,134 |
| 200 | 3,108 |
| 0 | 2,218 |
| 400 | 1,817 |
| 450 | 1,762 |
| 270 | 997 |
| 1 | 676 |

Top 20 of 31 distinct numeric values shown; all frequencies were calculated.


## Monetary Fields

### plan_list_price

#### transactions.csv

| Metric | Value |
| --- | ---: |
| Numeric rows | 21,547,746 |
| Minimum | 0 |
| Maximum | 2,000 |
| Rows < 0 | 0 |
| Rows = 0 | 1,498,544 |
| Rows > 0 | 20,049,202 |

Quantiles over numeric rows:

| Metric | Value |
| --- | ---: |
| p01 | 0 |
| p05 | 0 |
| p25 | 99 |
| median | 149 |
| p75 | 149 |
| p95 | 150 |
| p99 | 799 |

| Numeric source value | Rows |
| --- | ---: |
| 149 | 12,536,656 |
| 99 | 4,853,433 |
| 0 | 1,498,544 |
| 129 | 1,144,459 |
| 180 | 682,533 |
| 150 | 382,860 |
| 894 | 109,879 |
| 100 | 80,285 |
| 1788 | 80,066 |
| 536 | 43,506 |
| 119 | 32,280 |
| 480 | 22,977 |
| 1599 | 11,463 |
| 477 | 10,847 |
| 35 | 7,410 |
| 799 | 6,264 |
| 300 | 5,828 |
| 120 | 5,821 |
| 1200 | 5,486 |
| 298 | 5,272 |

Top 20 of 51 distinct numeric values shown; all frequencies were calculated.

#### transactions_v2.csv

| Metric | Value |
| --- | ---: |
| Numeric rows | 1,431,009 |
| Minimum | 0 |
| Maximum | 2,000 |
| Rows < 0 | 0 |
| Rows = 0 | 18,413 |
| Rows > 0 | 1,412,596 |

Quantiles over numeric rows:

| Metric | Value |
| --- | ---: |
| p01 | 0 |
| p05 | 99 |
| p25 | 99 |
| median | 149 |
| p75 | 149 |
| p95 | 1788 |
| p99 | 1788 |

| Numeric source value | Rows |
| --- | ---: |
| 149 | 594,395 |
| 99 | 407,750 |
| 180 | 115,660 |
| 1788 | 83,963 |
| 129 | 52,986 |
| 100 | 43,873 |
| 894 | 29,677 |
| 0 | 18,413 |
| 536 | 18,335 |
| 1599 | 14,727 |
| 477 | 7,891 |
| 1200 | 7,603 |
| 298 | 6,049 |
| 300 | 4,782 |
| 447 | 4,041 |
| 480 | 3,857 |
| 1299 | 3,052 |
| 930 | 2,796 |
| 600 | 2,729 |
| 150 | 2,144 |

Top 20 of 48 distinct numeric values shown; all frequencies were calculated.


### actual_amount_paid

#### transactions.csv

| Metric | Value |
| --- | ---: |
| Numeric rows | 21,547,746 |
| Minimum | 0 |
| Maximum | 2,000 |
| Rows < 0 | 0 |
| Rows = 0 | 1,196,876 |
| Rows > 0 | 20,350,870 |

Quantiles over numeric rows:

| Metric | Value |
| --- | ---: |
| p01 | 0 |
| p05 | 0 |
| p25 | 99 |
| median | 149 |
| p75 | 149 |
| p95 | 150 |
| p99 | 894 |

| Numeric source value | Rows |
| --- | ---: |
| 149 | 12,460,832 |
| 99 | 4,855,208 |
| 0 | 1,196,876 |
| 129 | 1,174,670 |
| 180 | 680,058 |
| 150 | 396,210 |
| 119 | 355,083 |
| 894 | 113,452 |
| 1788 | 83,991 |
| 100 | 80,969 |
| 536 | 44,805 |
| 480 | 23,170 |
| 1599 | 12,086 |
| 477 | 10,847 |
| 35 | 7,892 |
| 799 | 6,465 |
| 300 | 5,996 |
| 1200 | 5,526 |
| 298 | 5,272 |
| 930 | 5,121 |

Top 20 of 57 distinct numeric values shown; all frequencies were calculated.

#### transactions_v2.csv

| Metric | Value |
| --- | ---: |
| Numeric rows | 1,431,009 |
| Minimum | 0 |
| Maximum | 2,000 |
| Rows < 0 | 0 |
| Rows = 0 | 21,448 |
| Rows > 0 | 1,409,561 |

Quantiles over numeric rows:

| Metric | Value |
| --- | ---: |
| p01 | 0 |
| p05 | 99 |
| p25 | 99 |
| median | 149 |
| p75 | 149 |
| p95 | 1788 |
| p99 | 1788 |

| Numeric source value | Rows |
| --- | ---: |
| 149 | 589,691 |
| 99 | 408,561 |
| 180 | 112,512 |
| 1788 | 83,980 |
| 129 | 53,410 |
| 100 | 43,893 |
| 894 | 29,674 |
| 0 | 21,448 |
| 536 | 18,335 |
| 1599 | 14,719 |
| 477 | 7,891 |
| 1200 | 7,608 |
| 298 | 6,049 |
| 300 | 4,782 |
| 119 | 4,103 |
| 447 | 4,047 |
| 480 | 3,857 |
| 1299 | 3,052 |
| 930 | 2,796 |
| 600 | 2,729 |

Top 20 of 53 distinct numeric values shown; all frequencies were calculated.


### Price Relationship

Derived price difference = plan_list_price minus actual_amount_paid. This inspection difference is not an official discount measure.

#### transactions.csv

| Metric | Value |
| --- | ---: |
| Rows with two valid monetary integers | 21,547,746 |
| Actual paid = list price | 19,832,943 |
| Actual paid < list price | 857,381 |
| Actual paid > list price | 857,422 |
| Actual paid = 0 and list price > 0 | 555,600 |
| List price = 0 and actual paid > 0 | 857,268 |
| Both prices = 0 | 641,276 |
| Minimum derived price difference | -2,000 |
| Maximum derived price difference | 699 |
| Derived price difference > 0 | 857,381 |
| Derived price difference = 0 | 19,832,943 |
| Derived price difference < 0 | 857,422 |

#### transactions_v2.csv

| Metric | Value |
| --- | ---: |
| Rows with two valid monetary integers | 1,431,009 |
| Actual paid = list price | 1,419,106 |
| Actual paid < list price | 9,639 |
| Actual paid > list price | 2,264 |
| Actual paid = 0 and list price > 0 | 5,251 |
| List price = 0 and actual paid > 0 | 2,216 |
| Both prices = 0 | 16,197 |
| Minimum derived price difference | -1,788 |
| Maximum derived price difference | 1,599 |
| Derived price difference > 0 | 9,639 |
| Derived price difference = 0 | 1,419,106 |
| Derived price difference < 0 | 2,264 |

## Renewal and Cancellation Flags

### is_auto_renew

#### transactions.csv

| Metric | Value |
| --- | ---: |
| Rows = 0 (parsed integer) | 3,189,796 |
| Rows = 1 (parsed integer) | 18,357,950 |
| Numeric rows outside {0,1} | 0 |
| Non-empty rows outside valid binary {0,1} | 0 |
| Empty rows | 0 |
| Non-integer rows | 0 |

| Source value | Rows |
| --- | ---: |
| <code>1</code> | 18,357,950 |
| <code>0</code> | 3,189,796 |

#### transactions_v2.csv

| Metric | Value |
| --- | ---: |
| Rows = 0 (parsed integer) | 307,234 |
| Rows = 1 (parsed integer) | 1,123,775 |
| Numeric rows outside {0,1} | 0 |
| Non-empty rows outside valid binary {0,1} | 0 |
| Empty rows | 0 |
| Non-integer rows | 0 |

| Source value | Rows |
| --- | ---: |
| <code>1</code> | 1,123,775 |
| <code>0</code> | 307,234 |

### is_cancel

#### transactions.csv

| Metric | Value |
| --- | ---: |
| Rows = 0 (parsed integer) | 20,690,895 |
| Rows = 1 (parsed integer) | 856,851 |
| Numeric rows outside {0,1} | 0 |
| Non-empty rows outside valid binary {0,1} | 0 |
| Empty rows | 0 |
| Non-integer rows | 0 |

| Source value | Rows |
| --- | ---: |
| <code>0</code> | 20,690,895 |
| <code>1</code> | 856,851 |

#### transactions_v2.csv

| Metric | Value |
| --- | ---: |
| Rows = 0 (parsed integer) | 1,395,876 |
| Rows = 1 (parsed integer) | 35,133 |
| Numeric rows outside {0,1} | 0 |
| Non-empty rows outside valid binary {0,1} | 0 |
| Empty rows | 0 |
| Non-integer rows | 0 |

| Source value | Rows |
| --- | ---: |
| <code>0</code> | 1,395,876 |
| <code>1</code> | 35,133 |

### Joint valid-binary matrix

#### transactions.csv

| is_auto_renew | is_cancel | Rows |
| --- | --- | ---: |
| 0 | 0 | 3,189,786 |
| 0 | 1 | 10 |
| 1 | 0 | 17,501,109 |
| 1 | 1 | 856,841 |

#### transactions_v2.csv

| is_auto_renew | is_cancel | Rows |
| --- | --- | ---: |
| 0 | 0 | 307,234 |
| 0 | 1 | 0 |
| 1 | 0 | 1,088,642 |
| 1 | 1 | 35,133 |

## Transaction Dates

### transactions.csv

| Metric | Value |
| --- | ---: |
| Empty rows | 0 |
| Invalid non-empty rows | 0 |
| Valid-date rows | 21,547,746 |
| Minimum valid date | 2015-01-01 |
| Maximum valid date | 2017-02-28 |
| Distinct valid years | 3 |

| Valid year | Rows |
| --- | ---: |
| 2015 | 8,518,147 |
| 2016 | 11,105,786 |
| 2017 | 1,923,813 |

### transactions_v2.csv

| Metric | Value |
| --- | ---: |
| Empty rows | 0 |
| Invalid non-empty rows | 0 |
| Valid-date rows | 1,431,009 |
| Minimum valid date | 2015-01-01 |
| Maximum valid date | 2017-03-31 |
| Distinct valid years | 3 |

| Valid year | Rows |
| --- | ---: |
| 2015 | 71,366 |
| 2016 | 128,034 |
| 2017 | 1,231,609 |

## Membership Expiry Dates

### transactions.csv

| Metric | Value |
| --- | ---: |
| Empty rows | 0 |
| Invalid non-empty rows | 0 |
| Valid-date rows | 21,547,746 |
| Minimum valid date | 1970-01-01 |
| Maximum valid date | 2017-03-31 |
| Distinct valid years | 13 |

| Valid year | Rows |
| --- | ---: |
| 1970 | 1,776 |
| 1999 | 2 |
| 2005 | 1 |
| 2007 | 3 |
| 2008 | 1 |
| 2009 | 2 |
| 2010 | 3 |
| 2012 | 16 |
| 2013 | 3,165 |
| 2014 | 4,871 |
| 2015 | 7,354,389 |
| 2016 | 11,096,895 |
| 2017 | 3,086,622 |

| Metric | Value |
| --- | ---: |
| Expiry date = 1970-01-01 | 1,776 |
| Expiry date = 2036-10-15 | 0 |

### transactions_v2.csv

| Metric | Value |
| --- | ---: |
| Empty rows | 0 |
| Invalid non-empty rows | 0 |
| Valid-date rows | 1,431,009 |
| Minimum valid date | 2016-04-19 |
| Maximum valid date | 2036-10-15 |
| Distinct valid years | 20 |

| Valid year | Rows |
| --- | ---: |
| 2016 | 11 |
| 2017 | 1,354,731 |
| 2018 | 66,549 |
| 2019 | 6,735 |
| 2020 | 2,074 |
| 2021 | 604 |
| 2022 | 143 |
| 2023 | 41 |
| 2024 | 32 |
| 2025 | 20 |
| 2026 | 20 |
| 2027 | 32 |
| 2028 | 10 |
| 2030 | 1 |
| 2031 | 1 |
| 2032 | 1 |
| 2033 | 1 |
| 2034 | 1 |
| 2035 | 1 |
| 2036 | 1 |

| Metric | Value |
| --- | ---: |
| Expiry date = 1970-01-01 | 0 |
| Expiry date = 2036-10-15 | 1 |

## Transaction-to-Expiry Relationship

expiry_delta_days is membership_expire_date minus transaction_date, using only rows with two valid dates. All values below are in days.

### transactions.csv

| Metric | Value |
| --- | ---: |
| Numeric rows | 21,547,746 |
| Minimum | -17,217 |
| Maximum | 814 |
| Rows < 0 | 153,660 |
| Rows = 0 | 471,741 |
| Rows > 0 | 20,922,345 |
| Rows > 31 | 4,299,982 |
| Rows > 365 | 198,749 |
| Rows > 730 | 2,344 |
| Rows > 3650 | 0 |

Quantiles over valid date-pair rows:

| Metric | Value |
| --- | ---: |
| p01 | 0 |
| p05 | 7 |
| p25 | 30 |
| median | 31 |
| p75 | 31 |
| p95 | 55 |
| p99 | 348 |

### transactions_v2.csv

| Metric | Value |
| --- | ---: |
| Numeric rows | 1,431,009 |
| Minimum | -3 |
| Maximum | 7,303 |
| Rows < 0 | 5,106 |
| Rows = 0 | 17,700 |
| Rows > 0 | 1,408,203 |
| Rows > 31 | 569,085 |
| Rows > 365 | 184,134 |
| Rows > 730 | 50,121 |
| Rows > 3650 | 49 |

Quantiles over valid date-pair rows:

| Metric | Value |
| --- | ---: |
| p01 | 0 |
| p05 | 30 |
| p25 | 30 |
| median | 31 |
| p75 | 53 |
| p95 | 549 |
| p99 | 1067 |

## Cross-Field Checks

### transactions.csv

| Metric | Value |
| --- | ---: |
| Rows with numeric plan days and two valid dates | 21,547,746 |
| Expiry delta = payment_plan_days | 6,716,387 |
| Expiry delta < payment_plan_days | 3,587,269 |
| Expiry delta > payment_plan_days | 11,244,090 |
| Cancelled rows (is_cancel = 1) with two valid dates | 856,851 |
| Cancelled rows with expiry delta < 0 | 147,200 |
| Cancelled rows with expiry delta = 0 | 455,685 |
| Cancelled rows with expiry delta > 0 | 253,966 |

### transactions_v2.csv

| Metric | Value |
| --- | ---: |
| Rows with numeric plan days and two valid dates | 1,431,009 |
| Expiry delta = payment_plan_days | 405,903 |
| Expiry delta < payment_plan_days | 37,493 |
| Expiry delta > payment_plan_days | 987,613 |
| Cancelled rows (is_cancel = 1) with two valid dates | 35,133 |
| Cancelled rows with expiry delta < 0 | 5,104 |
| Cancelled rows with expiry delta = 0 | 17,665 |
| Cancelled rows with expiry delta > 0 | 12,364 |

## Data Quality Findings

- transactions.csv: 0 rows have at least one missing or non-integer monetary field; 0 rows have at least one missing or non-binary flag.
- transactions.csv: actual paid is below list price in 857,381 rows and above it in 857,422 rows among 21,547,746 valid monetary pairs.
- transactions.csv: 153,660 valid date pairs have negative expiry deltas and 0 exceed 3,650 days. Expiry dates 1970-01-01 and 2036-10-15 occur 1,776 and 0 times respectively.
- transactions_v2.csv: 0 rows have at least one missing or non-integer monetary field; 0 rows have at least one missing or non-binary flag.
- transactions_v2.csv: actual paid is below list price in 9,639 rows and above it in 2,264 rows among 1,431,009 valid monetary pairs.
- transactions_v2.csv: 5,106 valid date pairs have negative expiry deltas and 49 exceed 3,650 days. Expiry dates 1970-01-01 and 2036-10-15 occur 0 and 1 times respectively.

## Implications for fact_transaction

- Use the field-level parse counts and ranges to assess integer compatibility. Preserve raw source values alongside future typed values and explicit validation flags where needed; do not silently coerce or delete problematic records.
- Assess binary compatibility from the complete flag frequencies. Cancellation is not churn, and the cancellation/date checks are descriptive only.
- Zero and negative monetary values and differences from list price require interpretation before monetary business measures are defined. The derived price difference is not an official discount. Currency units, net revenue, MRR, and ARPU are not defined by this inspection.
- Calendar validity is separate from date plausibility. Negative or large expiry deltas and the explicitly counted expiry extremes are candidates for validation flags, not automatic grounds for deletion. Plan days need not equal expiry delta.
- Preserve both transaction files and source lineage. The verified zero exact full-row overlap does not justify customer/date deduplication or merging source records into one assumed business transaction.
- No final cleaning rules or SQL are introduced.
