# Power BI Dashboard Specification

## Scope and Source Strategy

Build one primary page named **Subscription Growth & Retention Overview** in
Power BI Import mode. Import only the compact objects below; do not import
`analytics.fact_transaction` to calculate dashboard summaries.

| Power BI source object | Rows | Purpose |
| --- | ---: | --- |
| `analytics.v_powerbi_overview_kpis` | 1 | Six overview KPI cards |
| `analytics.mv_powerbi_transaction_activity` | 28 | 27 monthly rows plus one all-time row |
| `analytics.v_churn_cohort_summary` | 2 | Existing cohort counts and churn rates |
| `analytics.mv_powerbi_churn_transitions` | 4 | Shared-user label transitions |
| `analytics.mv_powerbi_transaction_distributions` | 9 | Price and plan-day distributions |
| `analytics.mv_powerbi_churn_transaction_behavior` | 4 | Cohort-window behavior by churn label |

The existing `analytics.v_member_metadata_coverage` and
`analytics.v_churn_cohort_summary` are reused by the one-row overview view.
Existing source-level transaction summaries remain available for ad hoc quality
work, but their wide/source-specific grain is not needed on this page.

The four new materialized views contain only compact aggregates. They snapshot
the verified V1 source state and should be refreshed in PostgreSQL before a
Power BI refresh if upstream analytical data ever changes. Power BI does not
need a relationship between these independent summary datasets.

## Page Layout

- Top row: six KPI cards.
- Middle row: monthly transaction trend and churn-cohort comparison.
- Bottom row: churn transitions, price relationship, plan-day distribution,
  and churn-versus-transaction behavior.
- Keep all content on this single page. Use tooltips for supporting denominators
  instead of adding drill-through pages for V1.

## KPI Cards

All cards use `analytics.v_powerbi_overview_kpis`, which has exactly one row.

| Card title | Field | Exact definition | Format |
| --- | --- | --- | --- |
| Canonical Users | `canonical_user_count` | Count of distinct canonical `msno` values across the currently staged member, churn, and transaction sources | Whole number |
| Member Metadata Coverage | `member_metadata_coverage_rate` | Canonical users with a matching member record divided by all canonical users | Percentage, 2 decimals |
| February Churn Rate | `feb_churn_rate` | February 2017 cohort observations with `is_churn = true` divided by all February cohort observations | Percentage, 2 decimals |
| March Churn Rate | `mar_churn_rate` | March 2017 cohort observations with `is_churn = true` divided by all March cohort observations | Percentage, 2 decimals |
| Transaction Records | `transaction_records` | Count of all preserved rows from both registered transaction sources; not unique payments or revenue | Whole number |
| Transacting Users | `unique_transacting_users` | Distinct canonical users represented by at least one preserved transaction record | Whole number |

## Visual 1: Monthly Transaction Activity

- **Title:** Monthly Transaction Records and Transacting Users
- **Visual:** Line chart with two value series
- **Source:** `analytics.mv_powerbi_transaction_activity`
- **X-axis:** `transaction_month`, continuous month axis
- **Y-axis / values:** `transaction_records`; `unique_transacting_users`
- **Legend:** Automatic measure-name legend
- **Filter:** `period_grain = 'month'`
- **Tooltips:** `auto_renew_record_rate`, `cancellation_record_rate`
- **Metric definitions:** Transaction records are preserved source rows dated in
  the month. Unique transacting users are distinct `user_key` values in that
  month across both sources. Auto-renew and cancellation rates use monthly
  transaction records as denominator.

## Visual 2: Churn Cohort Outcomes

- **Title:** Churn and Retention by Expiry Cohort
- **Visual:** Line and clustered column chart
- **Source:** `analytics.v_churn_cohort_summary`
- **X-axis:** `expiry_cohort_month`
- **Column Y-axis / values:** `churned_count`; `non_churned_count`
- **Line Y-axis:** `churn_rate`
- **Legend:** Automatic series names for churned and non-churned columns
- **Filter:** None
- **Tooltips:** `observation_count`; `churn_rate`; calculated display value
  `1 - churn_rate` for the non-churn/retention rate
- **Metric definitions:** Each observation is one canonical user and expiry
  cohort. Churn rate is churned observations divided by all cohort observations;
  non-churn/retention rate is non-churned observations divided by the same
  denominator. The cohort month is not an exact churn date.

## Visual 3: Churn Transitions

- **Title:** February-to-March Churn Label Transitions
- **Visual:** Donut chart
- **Source:** `analytics.mv_powerbi_churn_transitions`
- **Category / legend:** `transition`, sorted by `transition_sort`
- **Y-axis / value:** `users`
- **Filter:** None
- **Tooltips:** `shared_user_rate`; `shared_users`; `feb_label`; `mar_label`
- **Metric definitions:** Users are counted only when present in both cohorts.
  `shared_user_rate` is each transition count divided by all shared users, not by
  either full cohort.

## Visual 4: Transaction Price Relationships

- **Title:** Paid Amount vs List Price
- **Visual:** Horizontal bar chart
- **Source:** `analytics.mv_powerbi_transaction_distributions`
- **Y-axis / category:** `category`, sorted by `category_sort`
- **X-axis / value:** `records`
- **Legend:** None
- **Filter:** `distribution = 'price_relationship'`
- **Tooltips:** `record_rate`; `distribution_records`
- **Metric definitions:** Categories compare `actual_amount_paid` with
  `plan_list_price` for each preserved transaction record. `record_rate` uses all
  preserved transaction records as denominator. The comparison is not a revenue
  or discount measure.

## Visual 5: Payment Plan Days

- **Title:** Payment Plan Day Distribution
- **Visual:** Clustered column chart
- **Source:** `analytics.mv_powerbi_transaction_distributions`
- **X-axis / category:** `category`, sorted by `category_sort`
- **Y-axis / value:** `records`
- **Legend:** None
- **Filter:** `distribution = 'payment_plan_days'`
- **Tooltips:** `record_rate`; `distribution_records`
- **Metric definitions:** Each record is assigned to exactly one source
  `payment_plan_days` band: 0, 1-29, 30, 31, 32-365, or over 365. Values are
  retained source characteristics, not validity classifications.

## Visual 6: Churn vs Transaction Behavior

- **Title:** Transaction Behavior by Churn Status
- **Visual:** Clustered bar chart with small multiples
- **Source:** `analytics.mv_powerbi_churn_transaction_behavior`
- **Y-axis / category:** `churn_status`
- **X-axis / values:** `users_with_transaction_record_rate`;
  `auto_renew_record_rate`; `cancellation_record_rate`
- **Small multiples:** `expiry_cohort_month`
- **Legend:** Automatic measure-name legend
- **Filter:** None
- **Tooltips:** `cohort_users`; `users_with_transaction_records`;
  `transaction_records`; `avg_records_per_transacting_user`
- **Metric definitions:** Each cohort uses the three calendar months ending with
  its expiry month: December-February or January-March. User coverage divides
  cohort users with at least one transaction record by all users in the displayed
  cohort/churn group. Auto-renew and cancellation rates divide the corresponding
  flagged records by all transaction records in that window and group.

These measures are descriptive associations. `is_cancel` is not churn, and the
visual must not use causal wording.

## Power BI Formatting and Modeling Notes

- Format all `*_rate` fields as percentages; do not multiply them by 100 again.
- Format counts with thousands separators and no decimal places.
- Mark `transaction_month` and `expiry_cohort_month` as dates and sort ascending.
- Sort transition and distribution labels with their explicit integer sort
  fields, then hide the sort fields from report view.
- Use concise tooltips that always expose the count denominator behind a rate.
- Do not create measures named revenue, MRR, ARPU, or LTV from this layer.
- Add a page subtitle: **Transaction metrics represent preserved source records,
  not proven unique payments.**
