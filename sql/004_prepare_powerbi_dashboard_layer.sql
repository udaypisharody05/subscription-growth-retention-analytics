-- Compact, import-ready Power BI presentation datasets for the finished V1.
-- Materialized summaries prevent routine dashboard refreshes from importing or
-- repeatedly aggregating the 22.98-million-row transaction-level view.

BEGIN;

DROP VIEW IF EXISTS analytics.v_powerbi_overview_kpis;
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_powerbi_churn_transaction_behavior;
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_powerbi_transaction_distributions;
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_powerbi_churn_transitions;
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_powerbi_transaction_activity;

CREATE MATERIALIZED VIEW analytics.mv_powerbi_transaction_activity AS
WITH transactions AS (
    SELECT
        date_trunc('month', transaction_date)::DATE AS transaction_month,
        user_key,
        is_auto_renew,
        is_cancel
    FROM analytics.fact_transaction
)
SELECT
    CASE WHEN GROUPING(transaction_month) = 1 THEN 'all_time' ELSE 'month' END
        AS period_grain,
    transaction_month,
    count(*) AS transaction_records,
    count(DISTINCT user_key) AS unique_transacting_users,
    count(*) FILTER (WHERE is_auto_renew) AS auto_renew_records,
    count(*) FILTER (WHERE is_auto_renew)::NUMERIC / NULLIF(count(*), 0)
        AS auto_renew_record_rate,
    count(*) FILTER (WHERE is_cancel) AS cancellation_records,
    count(*) FILTER (WHERE is_cancel)::NUMERIC / NULLIF(count(*), 0)
        AS cancellation_record_rate
FROM transactions
GROUP BY GROUPING SETS ((transaction_month), ());

CREATE UNIQUE INDEX powerbi_transaction_activity_grain_month_unique
    ON analytics.mv_powerbi_transaction_activity
    (period_grain, COALESCE(transaction_month, DATE '0001-01-01'));

COMMENT ON MATERIALIZED VIEW analytics.mv_powerbi_transaction_activity IS
    'Power BI monthly and all-time transaction-record activity; records are not defined as unique payments.';

CREATE MATERIALIZED VIEW analytics.mv_powerbi_churn_transitions AS
WITH transitions AS (
    SELECT
        feb.is_churn AS feb_is_churn,
        mar.is_churn AS mar_is_churn
    FROM analytics.fact_churn_observation AS feb
    JOIN analytics.fact_churn_observation AS mar USING (user_key)
    WHERE feb.expiry_cohort_month = DATE '2017-02-01'
      AND mar.expiry_cohort_month = DATE '2017-03-01'
), summarized AS (
    SELECT feb_is_churn, mar_is_churn, count(*) AS users
    FROM transitions
    GROUP BY feb_is_churn, mar_is_churn
)
SELECT
    CASE WHEN feb_is_churn THEN 'churn' ELSE 'non_churn' END AS feb_label,
    CASE WHEN mar_is_churn THEN 'churn' ELSE 'non_churn' END AS mar_label,
    CASE
        WHEN NOT feb_is_churn AND NOT mar_is_churn THEN 'non_churn_to_non_churn'
        WHEN NOT feb_is_churn AND mar_is_churn THEN 'non_churn_to_churn'
        WHEN feb_is_churn AND NOT mar_is_churn THEN 'churn_to_non_churn'
        ELSE 'churn_to_churn'
    END AS transition,
    CASE
        WHEN NOT feb_is_churn AND NOT mar_is_churn THEN 1
        WHEN NOT feb_is_churn AND mar_is_churn THEN 2
        WHEN feb_is_churn AND NOT mar_is_churn THEN 3
        ELSE 4
    END AS transition_sort,
    users,
    sum(users) OVER () AS shared_users,
    users::NUMERIC / NULLIF(sum(users) OVER (), 0) AS shared_user_rate
FROM summarized;

CREATE UNIQUE INDEX powerbi_churn_transitions_unique
    ON analytics.mv_powerbi_churn_transitions (feb_label, mar_label);

COMMENT ON MATERIALIZED VIEW analytics.mv_powerbi_churn_transitions IS
    'Power BI transition counts for users present in both expiry cohorts.';

CREATE MATERIALIZED VIEW analytics.mv_powerbi_transaction_distributions AS
WITH categorized AS (
    SELECT
        CASE
            WHEN payment_plan_days = 0 THEN '0'
            WHEN payment_plan_days BETWEEN 1 AND 29 THEN '01-29'
            WHEN payment_plan_days = 30 THEN '30'
            WHEN payment_plan_days = 31 THEN '31'
            WHEN payment_plan_days BETWEEN 32 AND 365 THEN '032-365'
            ELSE 'over_365'
        END AS plan_days_group,
        CASE
            WHEN payment_plan_days = 0 THEN 1
            WHEN payment_plan_days BETWEEN 1 AND 29 THEN 2
            WHEN payment_plan_days = 30 THEN 3
            WHEN payment_plan_days = 31 THEN 4
            WHEN payment_plan_days BETWEEN 32 AND 365 THEN 5
            ELSE 6
        END AS plan_days_sort,
        price_relationship
    FROM analytics.fact_transaction
), grouped AS (
    SELECT
        CASE WHEN GROUPING(plan_days_group) = 0
             THEN 'payment_plan_days' ELSE 'price_relationship' END AS distribution,
        COALESCE(plan_days_group, price_relationship) AS category,
        CASE
            WHEN GROUPING(plan_days_group) = 0 THEN max(plan_days_sort)
            WHEN price_relationship = 'equal' THEN 1
            WHEN price_relationship = 'paid_below_list' THEN 2
            ELSE 3
        END AS category_sort,
        count(*) AS records
    FROM categorized
    GROUP BY GROUPING SETS ((plan_days_group, plan_days_sort), (price_relationship))
)
SELECT
    distribution,
    category,
    category_sort,
    records,
    sum(records) OVER (PARTITION BY distribution) AS distribution_records,
    records::NUMERIC / NULLIF(sum(records) OVER (PARTITION BY distribution), 0)
        AS record_rate
FROM grouped;

CREATE UNIQUE INDEX powerbi_transaction_distributions_unique
    ON analytics.mv_powerbi_transaction_distributions (distribution, category);

COMMENT ON MATERIALIZED VIEW analytics.mv_powerbi_transaction_distributions IS
    'Power BI long-form payment-plan-day and price-relationship record distributions.';

CREATE MATERIALIZED VIEW analytics.mv_powerbi_churn_transaction_behavior AS
WITH cohort_users AS (
    SELECT user_key, expiry_cohort_month, is_churn
    FROM analytics.fact_churn_observation
), user_window_activity AS (
    SELECT
        c.user_key,
        c.expiry_cohort_month,
        c.is_churn,
        count(t.source_row_number) AS transaction_records,
        count(t.source_row_number) FILTER (WHERE t.is_auto_renew) AS auto_renew_records,
        count(t.source_row_number) FILTER (WHERE t.is_cancel) AS cancellation_records
    FROM cohort_users AS c
    LEFT JOIN analytics.fact_transaction AS t
      ON t.user_key = c.user_key
     AND t.transaction_date >= (c.expiry_cohort_month - INTERVAL '2 months')::DATE
     AND t.transaction_date < (c.expiry_cohort_month + INTERVAL '1 month')::DATE
    GROUP BY c.user_key, c.expiry_cohort_month, c.is_churn
)
SELECT
    expiry_cohort_month,
    CASE WHEN is_churn THEN 'churn' ELSE 'non_churn' END AS churn_status,
    is_churn,
    count(*) AS cohort_users,
    count(*) FILTER (WHERE transaction_records > 0) AS users_with_transaction_records,
    count(*) FILTER (WHERE transaction_records > 0)::NUMERIC / NULLIF(count(*), 0)
        AS users_with_transaction_record_rate,
    sum(transaction_records) AS transaction_records,
    avg(transaction_records) FILTER (WHERE transaction_records > 0)
        AS avg_records_per_transacting_user,
    sum(auto_renew_records)::NUMERIC / NULLIF(sum(transaction_records), 0)
        AS auto_renew_record_rate,
    sum(cancellation_records)::NUMERIC / NULLIF(sum(transaction_records), 0)
        AS cancellation_record_rate
FROM user_window_activity
GROUP BY expiry_cohort_month, is_churn;

CREATE UNIQUE INDEX powerbi_churn_transaction_behavior_unique
    ON analytics.mv_powerbi_churn_transaction_behavior
    (expiry_cohort_month, is_churn);

COMMENT ON MATERIALIZED VIEW analytics.mv_powerbi_churn_transaction_behavior IS
    'Power BI descriptive three-month transaction-record behavior by expiry cohort and churn label.';

CREATE VIEW analytics.v_powerbi_overview_kpis AS
WITH churn AS (
    SELECT
        max(churn_rate) FILTER (WHERE expiry_cohort_month = DATE '2017-02-01')
            AS feb_churn_rate,
        max(churn_rate) FILTER (WHERE expiry_cohort_month = DATE '2017-03-01')
            AS mar_churn_rate
    FROM analytics.v_churn_cohort_summary
)
SELECT
    m.canonical_user_count,
    m.member_metadata_coverage_rate,
    c.feb_churn_rate,
    c.mar_churn_rate,
    t.transaction_records,
    t.unique_transacting_users
FROM analytics.v_member_metadata_coverage AS m
CROSS JOIN churn AS c
CROSS JOIN analytics.mv_powerbi_transaction_activity AS t
WHERE t.period_grain = 'all_time';

COMMENT ON VIEW analytics.v_powerbi_overview_kpis IS
    'Single-row source for the six Power BI overview KPI cards.';

COMMIT;
