-- Core V1 analytics layer over the verified member, churn, and transaction staging data.
-- User-log identities are intentionally deferred until bounded activity aggregation exists.

BEGIN;

CREATE TABLE IF NOT EXISTS analytics.dim_user (
    user_key BIGINT GENERATED ALWAYS AS IDENTITY,
    msno TEXT NOT NULL,
    has_member_metadata BOOLEAN NOT NULL,
    city_code INTEGER,
    gender TEXT,
    registered_via_code INTEGER,
    registration_init_date DATE,
    bd_raw INTEGER,
    analytical_age SMALLINT GENERATED ALWAYS AS (
        CASE WHEN bd_raw BETWEEN 1 AND 100 THEN bd_raw::SMALLINT END
    ) STORED,
    age_quality TEXT GENERATED ALWAYS AS (
        CASE
            WHEN NOT has_member_metadata THEN 'no_member_metadata'
            WHEN bd_raw < 0 THEN 'negative'
            WHEN bd_raw = 0 THEN 'zero_or_unknown'
            WHEN bd_raw BETWEEN 1 AND 100 THEN 'valid'
            ELSE 'above_100'
        END
    ) STORED,

    CONSTRAINT dim_user_pkey PRIMARY KEY (user_key),
    CONSTRAINT dim_user_msno_unique UNIQUE (msno),
    CONSTRAINT dim_user_msno_nonempty CHECK (msno <> ''),
    CONSTRAINT dim_user_gender_nonempty CHECK (gender IS NULL OR gender <> ''),
    CONSTRAINT dim_user_member_fields_consistent CHECK (
        (has_member_metadata AND city_code IS NOT NULL AND bd_raw IS NOT NULL
            AND registered_via_code IS NOT NULL AND registration_init_date IS NOT NULL)
        OR
        (NOT has_member_metadata AND city_code IS NULL AND gender IS NULL
            AND registered_via_code IS NULL AND registration_init_date IS NULL
            AND bd_raw IS NULL)
    )
);

COMMENT ON TABLE analytics.dim_user IS
    'One canonical msno across currently staged V1 sources, with optional member enrichment.';
COMMENT ON COLUMN analytics.dim_user.analytical_age IS
    'Source bd retained only from 1 through 100 inclusive under a project convention.';
COMMENT ON COLUMN analytics.dim_user.age_quality IS
    'Explicit member-availability and bd quality category; not an official KKBox classification.';

-- Load members first so metadata is attached wherever available. Later inserts add
-- identities absent from members without overwriting member enrichment.
INSERT INTO analytics.dim_user (
    msno, has_member_metadata, city_code, gender, registered_via_code,
    registration_init_date, bd_raw
)
SELECT
    msno, TRUE, city_code, gender, registered_via_code,
    registration_init_date, bd_raw
FROM staging.members
ON CONFLICT (msno) DO UPDATE SET
    has_member_metadata = TRUE,
    city_code = EXCLUDED.city_code,
    gender = EXCLUDED.gender,
    registered_via_code = EXCLUDED.registered_via_code,
    registration_init_date = EXCLUDED.registration_init_date,
    bd_raw = EXCLUDED.bd_raw;

INSERT INTO analytics.dim_user (msno, has_member_metadata)
SELECT DISTINCT msno, FALSE
FROM staging.churn_labels
ON CONFLICT (msno) DO NOTHING;

INSERT INTO analytics.dim_user (msno, has_member_metadata)
SELECT DISTINCT msno, FALSE
FROM staging.transactions
ON CONFLICT (msno) DO NOTHING;

CREATE TABLE IF NOT EXISTS analytics.fact_churn_observation (
    user_key BIGINT NOT NULL,
    expiry_cohort_month DATE NOT NULL,
    is_churn BOOLEAN NOT NULL,
    label_source TEXT NOT NULL,
    source_file_key BIGINT NOT NULL,
    source_row_number BIGINT NOT NULL,

    CONSTRAINT fact_churn_observation_pkey
        PRIMARY KEY (user_key, expiry_cohort_month),
    CONSTRAINT fact_churn_observation_user_fk FOREIGN KEY (user_key)
        REFERENCES analytics.dim_user (user_key),
    CONSTRAINT fact_churn_observation_source_fk FOREIGN KEY (source_file_key)
        REFERENCES raw.source_file (source_file_key),
    CONSTRAINT fact_churn_observation_source_row_unique
        UNIQUE (source_file_key, source_row_number),
    CONSTRAINT fact_churn_observation_source_row_positive
        CHECK (source_row_number > 0),
    CONSTRAINT fact_churn_observation_cohort_start
        CHECK (EXTRACT(DAY FROM expiry_cohort_month) = 1),
    CONSTRAINT fact_churn_observation_known_cohort CHECK (
        (label_source = 'train.csv' AND expiry_cohort_month = DATE '2017-02-01')
        OR
        (label_source = 'train_v2.csv' AND expiry_cohort_month = DATE '2017-03-01')
    )
);

COMMENT ON TABLE analytics.fact_churn_observation IS
    'One canonical user and expiry-cohort churn observation; no exact churn date is available.';
COMMENT ON COLUMN analytics.fact_churn_observation.expiry_cohort_month IS
    'First-day cohort anchor; the outcome is evaluated over the following 30 days.';

INSERT INTO analytics.fact_churn_observation (
    user_key, expiry_cohort_month, is_churn, label_source,
    source_file_key, source_row_number
)
SELECT
    u.user_key, c.expiry_cohort_month, c.is_churn, sf.file_name,
    c.source_file_key, c.source_row_number
FROM staging.churn_labels AS c
JOIN analytics.dim_user AS u ON u.msno = c.msno
JOIN raw.source_file AS sf ON sf.source_file_key = c.source_file_key
ON CONFLICT (source_file_key, source_row_number) DO NOTHING;

-- A view avoids a redundant physical copy of all 22.98 million transaction rows.
CREATE OR REPLACE VIEW analytics.fact_transaction AS
SELECT
    t.source_file_key,
    t.source_row_number,
    sf.file_name AS source_file,
    u.user_key,
    t.msno,
    t.payment_method_id,
    t.payment_plan_days,
    t.plan_list_price,
    t.actual_amount_paid,
    t.is_auto_renew,
    t.transaction_date,
    t.membership_expire_date,
    t.is_cancel,
    t.price_difference,
    t.price_relationship,
    t.expiry_delta_days,
    t.has_negative_expiry_delta,
    t.has_zero_expiry_delta,
    t.has_long_expiry_delta,
    t.plan_expiry_relationship
FROM staging.transactions AS t
JOIN analytics.dim_user AS u ON u.msno = t.msno
JOIN raw.source_file AS sf ON sf.source_file_key = t.source_file_key;

COMMENT ON VIEW analytics.fact_transaction IS
    'Source-preserving transaction analytics view; monetary fields are not defined as revenue.';

CREATE OR REPLACE VIEW analytics.v_monthly_transaction_activity AS
SELECT
    date_trunc('month', transaction_date)::DATE AS transaction_month,
    source_file_key,
    source_file,
    count(*) AS transaction_count,
    count(DISTINCT user_key) AS distinct_users,
    count(*) FILTER (WHERE is_auto_renew) AS auto_renew_transaction_count,
    count(*) FILTER (WHERE is_cancel) AS cancellation_transaction_count,
    count(*) FILTER (WHERE has_negative_expiry_delta) AS negative_expiry_count,
    count(*) FILTER (WHERE has_zero_expiry_delta) AS zero_expiry_count,
    count(*) FILTER (WHERE has_long_expiry_delta) AS long_expiry_count
FROM analytics.fact_transaction
GROUP BY 1, 2, 3;

CREATE OR REPLACE VIEW analytics.v_churn_cohort_summary AS
SELECT
    expiry_cohort_month,
    count(*) AS observation_count,
    count(*) FILTER (WHERE is_churn) AS churned_count,
    count(*) FILTER (WHERE NOT is_churn) AS non_churned_count,
    count(*) FILTER (WHERE is_churn)::NUMERIC / NULLIF(count(*), 0) AS churn_rate
FROM analytics.fact_churn_observation
GROUP BY expiry_cohort_month;

CREATE OR REPLACE VIEW analytics.v_member_metadata_coverage AS
SELECT
    count(*) AS canonical_user_count,
    count(*) FILTER (WHERE has_member_metadata) AS users_with_member_metadata,
    count(*) FILTER (WHERE NOT has_member_metadata) AS users_without_member_metadata,
    count(*) FILTER (WHERE has_member_metadata)::NUMERIC / NULLIF(count(*), 0)
        AS member_metadata_coverage_rate
FROM analytics.dim_user;

CREATE OR REPLACE VIEW analytics.v_transaction_relationship_anomaly_summary AS
SELECT
    source_file_key,
    source_file,
    count(*) AS transaction_count,
    count(*) FILTER (WHERE price_relationship = 'equal') AS paid_equal_list_count,
    count(*) FILTER (WHERE price_relationship = 'paid_below_list') AS paid_below_list_count,
    count(*) FILTER (WHERE price_relationship = 'paid_above_list') AS paid_above_list_count,
    count(*) FILTER (WHERE plan_expiry_relationship = 'equal') AS plan_expiry_equal_count,
    count(*) FILTER (WHERE plan_expiry_relationship = 'expiry_shorter') AS expiry_shorter_count,
    count(*) FILTER (WHERE plan_expiry_relationship = 'expiry_longer') AS expiry_longer_count,
    count(*) FILTER (WHERE has_negative_expiry_delta) AS negative_expiry_count,
    count(*) FILTER (WHERE has_zero_expiry_delta) AS zero_expiry_count,
    count(*) FILTER (WHERE has_long_expiry_delta) AS long_expiry_count,
    count(*) FILTER (WHERE is_cancel) AS cancellation_count
FROM analytics.fact_transaction
GROUP BY source_file_key, source_file;

COMMIT;
