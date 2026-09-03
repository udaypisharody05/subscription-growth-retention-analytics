# fact_transaction Cleaning and Validation Policy

## 1. Principles

This policy uses the supplied verified full transaction-field profiling and source-overlap results. It documents future typed staging and `analytics.fact_transaction`; it does not implement SQL, transformations, or a revenue methodology.

- Preserve every source record and its source lineage.
- Use typed staging without destructive cleaning. Both sources have zero missing/non-integer values in all six profiled integer fields, only binary flags, and calendar-valid dates.
- Distinguish syntactic validity from analytical plausibility. Use descriptive validation flags rather than deleting records or nulling valid source values.
- Do not deduplicate on `(msno, transaction_date)` or collapse historical v2 records into original records.
- Preserve monetary source values without defining revenue, MRR, or ARPU.
- Preserve cancellation meaning separately from churn.

## 2. Proposed Transaction Fields

The fields below are conceptual proposals, not an implemented schema. Key-generation and user-key resolution details remain implementation decisions.

| Analytical field | Source / derivation | Treatment |
| --- | --- | --- |
| transaction_key | Generated surrogate for a preserved source record | Identifies a fact row, not a proven unique economic transaction across files. |
| user_key | Future user-key resolution from source msno | Link to the analytical user identity; retain source identity in staging and do not discard a source record because key resolution needs handling. |
| payment_method_id | Source payment_method_id | Preserve as a typed integer code without descriptive names. |
| payment_plan_days | Source payment_plan_days | Preserve as a typed integer, including zero and long durations. |
| plan_list_price | Source plan_list_price | Preserve as a typed integer; retain zero. |
| actual_amount_paid | Source actual_amount_paid | Preserve as a typed integer; retain zero; not yet defined as net revenue. |
| is_auto_renew | Source is_auto_renew | Boolean-compatible representation retaining original binary meaning. |
| is_cancel | Source is_cancel | Boolean-compatible representation; never rename to churn. |
| transaction_date | Source transaction_date | Parse YYYYMMDD to DATE without changing calendar-valid values. |
| membership_expire_date | Source membership_expire_date | Parse YYYYMMDD to DATE; preserve unusual valid dates. |
| source_file | Original filename | Distinguish transactions.csv from transactions_v2.csv. |
| source_file_key | Future identifier for the source file | Maintain an unambiguous link to source-file lineage. |
| source_row_number | Position of the data record within its source file | Proposed convention: one-based data-record number, excluding the header; interpreted with source-file identity. |
| price_relationship | Compare actual_amount_paid with plan_list_price | equal / paid_below_list / paid_above_list; descriptive only. |
| price_difference | plan_list_price - actual_amount_paid | Optional derived inspection/analytical difference, not an official discount. |
| expiry_delta_days | membership_expire_date - transaction_date | Signed difference in days; preserve the source dates. |
| has_negative_expiry_delta | expiry_delta_days < 0 | Descriptive validation flag, not an automatic error. |
| has_zero_expiry_delta | expiry_delta_days = 0 | Descriptive validation flag. |
| has_long_expiry_delta | expiry_delta_days > 730 | Project analytical validation threshold, not an official KKBox invalidity rule. |
| plan_expiry_relationship | Compare expiry_delta_days with payment_plan_days | equal / expiry_shorter / expiry_longer; no equality constraint. |

No `is_churn` field is proposed for this transaction record.

## 3. Source Preservation and Lineage

| Source file | Verified rows |
| --- | ---: |
| transactions.csv | 21,547,746 |
| transactions_v2.csv | 1,431,009 |

Every source row must be preserved with its file identity and row lineage. Both files remain independently traceable even if a future fact layer contains records from both.

Verified exact full-row overlap is zero. However, v2 is not a simple duplicate append, and this result does not establish economic independence between the files. Do not collapse historical v2 rows into original rows or deduplicate on customer/date keys. Source-file identity plus source-row position identifies a source record, not an economic deduplication rule.

## 4. Numeric Source Fields

Both files have zero missing/non-integer values for `payment_method_id`, `payment_plan_days`, `plan_list_price`, `actual_amount_paid`, `is_auto_renew`, and `is_cancel`. These findings support typed staging while retaining the untouched raw sources and source lineage.

| Verified measure | transactions.csv | transactions_v2.csv |
| --- | ---: | ---: |
| payment_method_id range | 1-41 | 2-41 |
| Distinct payment_method_id values | 40 | 37 |
| payment_plan_days range | 0-450 | 0-450 |
| payment_plan_days = 0 | 870,124 | 2,218 |
| payment_plan_days = 30 | 18,956,290 | 1,217,998 |
| payment_plan_days > 31 | 326,729 | 197,427 |
| payment_plan_days > 365 | 94,058 | 98,727 |

Preserve `payment_method_id` as an integer code; do not invent categorical meanings or payment-method names. Preserve `payment_plan_days` as its typed source value. No negative plan durations exist in the verified sources. Zero and long plans are not automatically invalid, and observed ranges are not permanent business-validity constraints.

Both monetary fields are non-negative integers with range 0-2000 in both files. Preserve them unchanged as typed integers. Do not infer currency units.

## 5. Monetary Validation

| Verified measure | transactions.csv | transactions_v2.csv |
| --- | ---: | ---: |
| plan_list_price = 0 | 1,498,544 | 18,413 |
| actual_amount_paid = 0 | 1,196,876 | 21,448 |
| Paid = list | 19,832,943 | 1,419,106 |
| Paid < list | 857,381 | 9,639 |
| Paid > list | 857,422 | 2,264 |
| Paid = 0 and list > 0 | 555,600 | 5,251 |
| List = 0 and paid > 0 | 857,268 | 2,216 |
| Both = 0 | 641,276 | 16,197 |
| Derived list-minus-paid minimum | -2000 | -1788 |
| Derived list-minus-paid maximum | 699 | 1599 |

Retain zeros; do not convert them to NULL. Do not force paid and list values to match. No row is rejected solely because paid differs from list.

Define the descriptive category `price_relationship` as:

- `equal`: actual_amount_paid = plan_list_price.
- `paid_below_list`: actual_amount_paid < plan_list_price.
- `paid_above_list`: actual_amount_paid > plan_list_price.

Optionally retain `price_difference = plan_list_price - actual_amount_paid` as a derived inspection/analytical difference. It is not an official discount and may be negative.

`actual_amount_paid` is NOT yet declared to be net revenue. Do not define MRR or ARPU from this field yet, and do not assign currency units without separate verification.

## 6. Binary Flags

Both sources contain only 0/1 for `is_auto_renew` and `is_cancel`. Future typed staging may represent them as boolean-compatible values, mapping 0 to false and 1 to true while preserving each field's original binary meaning.

`is_cancel != churn`. Never rename cancellation to churn or infer churn from cancellation. These flags do not establish a churn outcome.

## 7. Date Treatment

Both source date fields contain only valid calendar dates. Parse their YYYYMMDD representations to DATE and preserve every calendar-valid value.

| Verified measure | transactions.csv | transactions_v2.csv |
| --- | --- | --- |
| transaction_date minimum | 2015-01-01 | 2015-01-01 |
| transaction_date maximum | 2017-02-28 | 2017-03-31 |
| membership_expire_date minimum | 1970-01-01 | 2016-04-19 |
| membership_expire_date maximum | 2017-03-31 | 2036-10-15 |

Exactly 1,776 original-file rows have expiry date 1970-01-01, and exactly 1 v2 row has expiry date 2036-10-15. These dates are calendar-valid but require plausibility investigation. Do not automatically remove, replace, or null either value. Use descriptive flags and derived measures to expose unusual relationships while preserving the dates.

## 8. Expiry Delta Validation

Derive `expiry_delta_days = membership_expire_date - transaction_date` in days.

| Verified measure | transactions.csv | transactions_v2.csv |
| --- | ---: | ---: |
| Minimum delta | -17,217 | -3 |
| Maximum delta | 814 | 7,303 |
| Delta < 0 | 153,660 | 5,106 |
| Delta = 0 | 471,741 | 17,700 |
| Delta > 365 | 198,749 | 184,134 |
| Delta > 730 | 2,344 | 50,121 |

In transactions_v2.csv, 49 rows have delta > 3650.

| Validation flag | Definition | Interpretation |
| --- | --- | --- |
| has_negative_expiry_delta | expiry_delta_days < 0 | Expiry precedes the transaction date; descriptive, not necessarily erroneous. |
| has_zero_expiry_delta | expiry_delta_days = 0 | Expiry and transaction dates are equal. |
| has_long_expiry_delta | expiry_delta_days > 730 | Flags durations beyond a fixed 730-day, approximately two-year threshold. |

The strictly greater-than-730-day threshold is a project analytical validation convention selected from the explicitly profiled thresholds, NOT an official KKBox invalidity rule. It is a fixed day count, not a calendar-anniversary calculation; a delta of exactly 730 days is not flagged as long.

Do not null source dates or delete records based on these flags. Negative deltas are not necessarily errors: the relevant cancellation, plan-change, and source-record semantics have not been fully established. The flags do not assert a cause.

## 9. Plan vs Expiry Relationship

| Descriptive category | Definition | transactions.csv | transactions_v2.csv |
| --- | --- | ---: | ---: |
| equal | expiry_delta_days = payment_plan_days | 6,716,387 | 405,903 |
| expiry_shorter | expiry_delta_days < payment_plan_days | 3,587,269 | 37,493 |
| expiry_longer | expiry_delta_days > payment_plan_days | 11,244,090 | 987,613 |

Use `plan_expiry_relationship` only as a descriptive comparison. Do not assume plan days must equal expiry delta, enforce equality, or treat inequality as an error. Preserve both the plan duration and the source dates used to derive the delta.

## 10. Cancellation Handling

| Verified cancelled-row measure | transactions.csv | transactions_v2.csv |
| --- | ---: | ---: |
| Total is_cancel = 1 rows | 856,851 | 35,133 |
| Expiry delta < 0 | 147,200 | 5,104 |
| Expiry delta = 0 | 455,685 | 17,665 |
| Expiry delta > 0 | 253,966 | 12,364 |

Preserve `is_cancel` and all cancelled transactions. These date relationships are descriptive only: do not infer churn, delete cancelled transactions, or assume a cancellation explains a particular expiry relationship.

## 11. Revenue Limitation

`plan_list_price` and `actual_amount_paid` are preserved monetary source fields, not established financial KPI definitions.

The source-file relationship is not yet sufficiently established to sum both files blindly into one economic revenue series. Historical v2 rows may represent additional or refreshed transaction records, but that possibility is not a verified interpretation, and no economic deduplication rule has been established. Zero exact full-row overlap does not resolve this economic relationship.

Therefore total revenue, MRR, ARPU, and other financial KPIs must wait for a separately documented revenue methodology. This policy does not create that methodology, define net revenue, assign currency units, or authorize financial aggregation across both files.

## 12. Final Policy Summary

| Area | Policy |
| --- | --- |
| Record grain and lineage | Preserve every source record; distinguish both files and source-row positions. |
| Source overlap | No customer/date deduplication or collapse of historical v2 records. |
| Typed staging | Parse syntactically valid fields without destructive cleaning; retain raw sources and lineage. |
| Payment method | Preserve integer codes without invented meanings. |
| Plan days | Preserve zero and long values; do not automatically classify them as invalid. |
| Monetary values | Preserve both integers, zeros, and mismatches; no forced equality or zero-to-NULL conversion. |
| Price comparison | Use descriptive categories; optional difference is not an official discount. |
| Binary flags | Preserve boolean-compatible source meaning; cancellation is not churn. |
| Dates | Preserve all calendar-valid values, including unusual extremes. |
| Expiry delta | Derive signed days and negative/zero/>730-day flags; flags do not justify deletion or nulling. |
| Plan/expiry comparison | Descriptive categories only; do not enforce equality. |
| Cancellation | Retain cancelled records; do not derive churn. |
| Financial KPIs | Defer revenue, MRR, ARPU, currency interpretation, and economic deduplication to separate methodology. |

No SQL or data transformation is implemented by this document.
