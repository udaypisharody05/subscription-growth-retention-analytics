# KKBox Churn Label Semantics

## Churn Definition

A customer is considered churned if they do not establish a valid renewal within 30 days after the relevant membership expiration. Churn is therefore evaluated using the renewal outcome following that expiration, not cancellation alone.

`is_cancel` is not equivalent to churn. A cancellation can occur during plan changes or other subscription events and does not necessarily imply that the customer fails to renew within the 30-day window.

## Label Files

| Source file | Expiry cohort | Outcome window interpretation |
| --- | --- | --- |
| train.csv | 2017-02 expiry cohort | Renewal or churn is evaluated over the following 30 days after the relevant membership expiration. |
| train_v2.csv | 2017-03 expiry cohort | Renewal or churn is evaluated over the following 30 days after the relevant membership expiration. |

These are membership-expiry cohorts, not rigid calendar-month outcome labels.

## Why Churn Is Time-Dependent

The verified label comparison found:

- 881,701 users appear in both label files.
- 45,990 shared users (5.22%) change labels.
- 40,721 users transition from 0 -> 1.
- 5,269 users transition from 1 -> 0.

The same customer can therefore have different churn outcomes for different subscription-expiry cohorts. Churn must be modeled as a time-dependent observation rather than a permanent customer characteristic.

## Modeling Decision

The future analytical model should conceptually represent churn as `fact_churn_observation`, with these fields:

- `msno`
- `expiry_cohort_month`
- `is_churn`
- `label_source`

`is_churn` must NOT be stored as a permanent attribute on `dim_users`.

This is a conceptual modeling decision only; no SQL tables are created at this stage.

## Important Limitation

`expiry_cohort_month` identifies the cohort used for labeling. The actual 30-day outcome window is relative to the relevant membership expiration and can extend into the following month; it is not restricted to the expiry cohort's calendar month.

The label files do not provide an exact churn event date. Neither the expiry cohort month nor the binary churn label should be treated as an exact churn event date.
