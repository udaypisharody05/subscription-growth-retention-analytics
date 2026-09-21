-- Core V1 product and subscription analysis.
-- Transaction counts represent preserved source records across both registered files;
-- they are not declared to be unique economic payments or revenue events.

BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = 0;

-- 1. Canonical user universe and optional member-enrichment coverage.
SELECT
    canonical_user_count,
    users_with_member_metadata,
    users_without_member_metadata,
    round(100 * member_metadata_coverage_rate, 4) AS metadata_coverage_pct
FROM analytics.v_member_metadata_coverage;

-- 2. Churn and non-churn (retention-label) outcomes by expiry cohort.
SELECT
    expiry_cohort_month,
    observation_count AS cohort_users,
    churned_count,
    non_churned_count,
    round(100.0 * churned_count / NULLIF(observation_count, 0), 4) AS churn_rate_pct,
    round(100.0 * non_churned_count / NULLIF(observation_count, 0), 4)
        AS non_churn_retention_rate_pct
FROM analytics.v_churn_cohort_summary
ORDER BY expiry_cohort_month;

-- 3. Label movement for users observed in both expiry cohorts.
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
    users,
    sum(users) OVER () AS shared_users,
    round(100.0 * users / NULLIF(sum(users) OVER (), 0), 4) AS shared_user_pct
FROM summarized
ORDER BY feb_is_churn, mar_is_churn;

-- 4a. Gender/member-availability groups by cohort. Sample size is always shown.
SELECT
    f.expiry_cohort_month,
    CASE
        WHEN NOT u.has_member_metadata THEN 'no_member_metadata'
        WHEN u.gender IS NULL THEN 'missing_gender'
        ELSE u.gender
    END AS gender_group,
    count(*) AS cohort_users,
    count(*) FILTER (WHERE f.is_churn) AS churned_users,
    round(100.0 * count(*) FILTER (WHERE f.is_churn) / NULLIF(count(*), 0), 4)
        AS churn_rate_pct
FROM analytics.fact_churn_observation AS f
JOIN analytics.dim_user AS u USING (user_key)
GROUP BY f.expiry_cohort_month, gender_group
ORDER BY f.expiry_cohort_month, cohort_users DESC, gender_group;

-- 4b. Opaque city codes by cohort. Codes are not mapped to city names.
SELECT
    f.expiry_cohort_month,
    CASE WHEN u.has_member_metadata THEN u.city_code::TEXT ELSE 'no_member_metadata' END
        AS city_group,
    count(*) AS cohort_users,
    count(*) FILTER (WHERE f.is_churn) AS churned_users,
    round(100.0 * count(*) FILTER (WHERE f.is_churn) / NULLIF(count(*), 0), 4)
        AS churn_rate_pct
FROM analytics.fact_churn_observation AS f
JOIN analytics.dim_user AS u USING (user_key)
GROUP BY f.expiry_cohort_month, city_group
ORDER BY f.expiry_cohort_month, cohort_users DESC, city_group;

-- 4c. Age-quality groups by cohort.
SELECT
    f.expiry_cohort_month,
    u.age_quality,
    count(*) AS cohort_users,
    count(*) FILTER (WHERE f.is_churn) AS churned_users,
    round(100.0 * count(*) FILTER (WHERE f.is_churn) / NULLIF(count(*), 0), 4)
        AS churn_rate_pct
FROM analytics.fact_churn_observation AS f
JOIN analytics.dim_user AS u USING (user_key)
GROUP BY f.expiry_cohort_month, u.age_quality
ORDER BY f.expiry_cohort_month, cohort_users DESC, u.age_quality;

-- 4d. Age bands include only ages accepted by the documented 1-100 convention.
SELECT
    f.expiry_cohort_month,
    CASE
        WHEN u.analytical_age BETWEEN 1 AND 17 THEN '01-17'
        WHEN u.analytical_age BETWEEN 18 AND 24 THEN '18-24'
        WHEN u.analytical_age BETWEEN 25 AND 34 THEN '25-34'
        WHEN u.analytical_age BETWEEN 35 AND 44 THEN '35-44'
        WHEN u.analytical_age BETWEEN 45 AND 54 THEN '45-54'
        WHEN u.analytical_age BETWEEN 55 AND 64 THEN '55-64'
        ELSE '65-100'
    END AS valid_age_band,
    count(*) AS cohort_users,
    count(*) FILTER (WHERE f.is_churn) AS churned_users,
    round(100.0 * count(*) FILTER (WHERE f.is_churn) / NULLIF(count(*), 0), 4)
        AS churn_rate_pct
FROM analytics.fact_churn_observation AS f
JOIN analytics.dim_user AS u USING (user_key)
WHERE u.analytical_age IS NOT NULL
GROUP BY f.expiry_cohort_month, valid_age_band
ORDER BY f.expiry_cohort_month, valid_age_band;

-- 4e. Opaque registration-channel codes by cohort.
SELECT
    f.expiry_cohort_month,
    CASE WHEN u.has_member_metadata THEN u.registered_via_code::TEXT
         ELSE 'no_member_metadata' END AS registered_via_group,
    count(*) AS cohort_users,
    count(*) FILTER (WHERE f.is_churn) AS churned_users,
    round(100.0 * count(*) FILTER (WHERE f.is_churn) / NULLIF(count(*), 0), 4)
        AS churn_rate_pct
FROM analytics.fact_churn_observation AS f
JOIN analytics.dim_user AS u USING (user_key)
GROUP BY f.expiry_cohort_month, registered_via_group
ORDER BY f.expiry_cohort_month, cohort_users DESC, registered_via_group;

-- 5a/6. Transaction coverage, flags, and anomaly indicators overall and by source.
SELECT
    COALESCE(source_file, 'all_sources') AS source_scope,
    count(*) AS transaction_records,
    count(DISTINCT user_key) AS distinct_transacting_users,
    count(*) FILTER (WHERE is_auto_renew) AS auto_renew_records,
    round(100.0 * count(*) FILTER (WHERE is_auto_renew) / NULLIF(count(*), 0), 4)
        AS auto_renew_record_pct,
    count(*) FILTER (WHERE is_cancel) AS cancellation_records,
    round(100.0 * count(*) FILTER (WHERE is_cancel) / NULLIF(count(*), 0), 4)
        AS cancellation_record_pct,
    count(*) FILTER (WHERE has_negative_expiry_delta) AS negative_expiry_records,
    round(100.0 * count(*) FILTER (WHERE has_negative_expiry_delta)
        / NULLIF(count(*), 0), 4) AS negative_expiry_pct,
    count(*) FILTER (WHERE has_zero_expiry_delta) AS zero_expiry_records,
    round(100.0 * count(*) FILTER (WHERE has_zero_expiry_delta)
        / NULLIF(count(*), 0), 4) AS zero_expiry_pct,
    count(*) FILTER (WHERE has_long_expiry_delta) AS over_730_day_expiry_records,
    round(100.0 * count(*) FILTER (WHERE has_long_expiry_delta)
        / NULLIF(count(*), 0), 4) AS over_730_day_expiry_pct,
    count(*) FILTER (WHERE price_relationship = 'paid_below_list') AS paid_below_list_records,
    count(*) FILTER (WHERE price_relationship = 'paid_above_list') AS paid_above_list_records,
    count(*) FILTER (WHERE actual_amount_paid = 0) AS zero_actual_payment_records
FROM analytics.fact_transaction
GROUP BY GROUPING SETS ((source_file), ());

-- 5b. Combined monthly transaction-record activity across both preserved sources.
SELECT
    date_trunc('month', transaction_date)::DATE AS transaction_month,
    count(*) AS transaction_records,
    count(DISTINCT user_key) AS unique_transacting_users,
    count(*) FILTER (WHERE is_auto_renew) AS auto_renew_records,
    round(100.0 * count(*) FILTER (WHERE is_auto_renew) / NULLIF(count(*), 0), 4)
        AS auto_renew_record_pct,
    count(*) FILTER (WHERE is_cancel) AS cancellation_records,
    round(100.0 * count(*) FILTER (WHERE is_cancel) / NULLIF(count(*), 0), 4)
        AS cancellation_record_pct
FROM analytics.fact_transaction
GROUP BY transaction_month
ORDER BY transaction_month;

-- 5c. Three deterministic transaction relationship distributions in one scan.
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
        price_relationship,
        plan_expiry_relationship
    FROM analytics.fact_transaction
), grouped AS (
    SELECT
        CASE
            WHEN GROUPING(plan_days_group) = 0 THEN 'payment_plan_days'
            WHEN GROUPING(price_relationship) = 0 THEN 'price_relationship'
            ELSE 'plan_expiry_relationship'
        END AS distribution,
        COALESCE(plan_days_group, price_relationship, plan_expiry_relationship) AS category,
        count(*) AS records
    FROM categorized
    GROUP BY GROUPING SETS ((plan_days_group), (price_relationship),
                            (plan_expiry_relationship))
)
SELECT
    distribution,
    category,
    records,
    sum(records) OVER (PARTITION BY distribution) AS distribution_records,
    round(100.0 * records / NULLIF(sum(records) OVER (PARTITION BY distribution), 0), 4)
        AS record_pct
FROM grouped
ORDER BY distribution, records DESC, category;

-- 7. Descriptive transaction history by churn outcome. Each cohort uses the three
-- calendar months ending with its expiry cohort month: Dec-Feb and Jan-Mar.
-- Counts remain source-record counts; the two transaction sources are not deduplicated.
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
    is_churn,
    count(*) AS cohort_users,
    count(*) FILTER (WHERE transaction_records > 0) AS users_with_transaction_records,
    round(100.0 * count(*) FILTER (WHERE transaction_records > 0)
        / NULLIF(count(*), 0), 4) AS users_with_transaction_record_pct,
    sum(transaction_records) AS transaction_records,
    round(avg(transaction_records) FILTER (WHERE transaction_records > 0), 4)
        AS avg_records_per_transacting_user,
    round(100.0 * sum(auto_renew_records) / NULLIF(sum(transaction_records), 0), 4)
        AS auto_renew_record_pct,
    round(100.0 * sum(cancellation_records) / NULLIF(sum(transaction_records), 0), 4)
        AS cancellation_record_pct
FROM user_window_activity
GROUP BY expiry_cohort_month, is_churn
ORDER BY expiry_cohort_month, is_churn;

ROLLBACK;
