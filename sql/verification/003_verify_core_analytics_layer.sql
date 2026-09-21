-- Deterministic verification for migration 003. This script is read-only.

BEGIN TRANSACTION READ ONLY;

DO $$
DECLARE
    dim_rows BIGINT;
    distinct_keys BIGINT;
    distinct_msnos BIGINT;
    with_metadata BIGINT;
    without_metadata BIGINT;
    churn_rows BIGINT;
    feb_rows BIGINT;
    mar_rows BIGINT;
    feb_churned BIGINT;
    feb_not_churned BIGINT;
    mar_churned BIGINT;
    mar_not_churned BIGINT;
    original_transactions BIGINT;
    v2_transactions BIGINT;
BEGIN
    IF to_regclass('analytics.dim_user') IS NULL
       OR to_regclass('analytics.fact_churn_observation') IS NULL
       OR to_regclass('analytics.fact_transaction') IS NULL
       OR to_regclass('analytics.v_monthly_transaction_activity') IS NULL
       OR to_regclass('analytics.v_churn_cohort_summary') IS NULL
       OR to_regclass('analytics.v_member_metadata_coverage') IS NULL
       OR to_regclass('analytics.v_transaction_relationship_anomaly_summary') IS NULL
    THEN
        RAISE EXCEPTION 'One or more migration 003 analytics objects are missing';
    END IF;

    IF (SELECT count(*) FROM raw.source_file) <> 7
       OR (SELECT count(*) FROM staging.members) <> 6769473
       OR (SELECT count(*) FROM staging.churn_labels) <> 1963891
       OR (SELECT count(*) FROM staging.transactions) <> 22978755
    THEN
        RAISE EXCEPTION 'A verified raw/staging row count changed';
    END IF;

    SELECT count(*), count(DISTINCT user_key), count(DISTINCT msno),
           count(*) FILTER (WHERE has_member_metadata),
           count(*) FILTER (WHERE NOT has_member_metadata)
    INTO dim_rows, distinct_keys, distinct_msnos, with_metadata, without_metadata
    FROM analytics.dim_user;

    IF dim_rows <> distinct_keys OR dim_rows <> distinct_msnos THEN
        RAISE EXCEPTION 'dim_user does not have one row per key and canonical msno';
    END IF;

    IF EXISTS (
        WITH canonical AS MATERIALIZED (
            SELECT msno FROM staging.members
            UNION
            SELECT msno FROM staging.churn_labels
            UNION
            SELECT msno FROM staging.transactions
        ), differences AS (
            (SELECT msno FROM canonical EXCEPT SELECT msno FROM analytics.dim_user)
            UNION ALL
            (SELECT msno FROM analytics.dim_user EXCEPT SELECT msno FROM canonical)
        )
        SELECT 1 FROM differences LIMIT 1
    ) THEN
        RAISE EXCEPTION 'dim_user differs from the currently staged canonical universe';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM analytics.dim_user AS u
        LEFT JOIN staging.members AS m ON m.msno = u.msno
        WHERE u.has_member_metadata IS DISTINCT FROM (m.msno IS NOT NULL)
           OR u.city_code IS DISTINCT FROM m.city_code
           OR u.gender IS DISTINCT FROM m.gender
           OR u.registered_via_code IS DISTINCT FROM m.registered_via_code
           OR u.registration_init_date IS DISTINCT FROM m.registration_init_date
           OR u.bd_raw IS DISTINCT FROM m.bd_raw
        LIMIT 1
    ) THEN
        RAISE EXCEPTION 'dim_user member LEFT JOIN enrichment is inconsistent';
    END IF;

    IF EXISTS (
        SELECT 1 FROM analytics.dim_user
        WHERE analytical_age IS DISTINCT FROM
              CASE WHEN bd_raw BETWEEN 1 AND 100 THEN bd_raw::SMALLINT END
           OR age_quality IS DISTINCT FROM CASE
                WHEN NOT has_member_metadata THEN 'no_member_metadata'
                WHEN bd_raw < 0 THEN 'negative'
                WHEN bd_raw = 0 THEN 'zero_or_unknown'
                WHEN bd_raw BETWEEN 1 AND 100 THEN 'valid'
                ELSE 'above_100' END
        LIMIT 1
    ) THEN
        RAISE EXCEPTION 'dim_user age convention is inconsistent';
    END IF;

    SELECT count(*),
           count(*) FILTER (WHERE expiry_cohort_month = DATE '2017-02-01'),
           count(*) FILTER (WHERE expiry_cohort_month = DATE '2017-03-01'),
           count(*) FILTER (WHERE expiry_cohort_month = DATE '2017-02-01' AND is_churn),
           count(*) FILTER (WHERE expiry_cohort_month = DATE '2017-02-01' AND NOT is_churn),
           count(*) FILTER (WHERE expiry_cohort_month = DATE '2017-03-01' AND is_churn),
           count(*) FILTER (WHERE expiry_cohort_month = DATE '2017-03-01' AND NOT is_churn)
    INTO churn_rows, feb_rows, mar_rows, feb_churned, feb_not_churned,
         mar_churned, mar_not_churned
    FROM analytics.fact_churn_observation;

    IF churn_rows <> 1963891 OR feb_rows <> 992931 OR mar_rows <> 970960 THEN
        RAISE EXCEPTION 'Churn observation or cohort row counts are incorrect';
    END IF;

    IF EXISTS (
        (SELECT source_file_key, source_row_number, msno, is_churn, expiry_cohort_month
         FROM staging.churn_labels
         EXCEPT
         SELECT f.source_file_key, f.source_row_number, u.msno, f.is_churn,
                f.expiry_cohort_month
         FROM analytics.fact_churn_observation AS f
         JOIN analytics.dim_user AS u ON u.user_key = f.user_key)
        UNION ALL
        (SELECT f.source_file_key, f.source_row_number, u.msno, f.is_churn,
                f.expiry_cohort_month
         FROM analytics.fact_churn_observation AS f
         JOIN analytics.dim_user AS u ON u.user_key = f.user_key
         EXCEPT
         SELECT source_file_key, source_row_number, msno, is_churn, expiry_cohort_month
         FROM staging.churn_labels)
        LIMIT 1
    ) THEN
        RAISE EXCEPTION 'Churn facts do not exactly preserve staging observations and lineage';
    END IF;

    IF EXISTS (
        SELECT user_key, expiry_cohort_month
        FROM analytics.fact_churn_observation
        GROUP BY user_key, expiry_cohort_month
        HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION 'Duplicate user/cohort churn facts exist';
    END IF;

    IF EXISTS (
        (SELECT expiry_cohort_month, is_churn, count(*)
         FROM analytics.fact_churn_observation GROUP BY 1, 2
         EXCEPT
         SELECT expiry_cohort_month, is_churn, count(*)
         FROM staging.churn_labels GROUP BY 1, 2)
        UNION ALL
        (SELECT expiry_cohort_month, is_churn, count(*)
         FROM staging.churn_labels GROUP BY 1, 2
         EXCEPT
         SELECT expiry_cohort_month, is_churn, count(*)
         FROM analytics.fact_churn_observation GROUP BY 1, 2)
    ) THEN
        RAISE EXCEPTION 'Churn TRUE/FALSE counts differ from verified staging values';
    END IF;

    SELECT
        count(*) FILTER (WHERE source_file = 'transactions.csv'),
        count(*) FILTER (WHERE source_file = 'transactions_v2.csv')
    INTO original_transactions, v2_transactions
    FROM analytics.fact_transaction;

    IF original_transactions <> 21547746 OR v2_transactions <> 1431009 THEN
        RAISE EXCEPTION 'Transaction view does not preserve both complete source versions';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'analytics' AND table_name = 'dim_user'
          AND column_name = 'is_churn'
    ) OR EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'analytics' AND table_name = 'fact_churn_observation'
          AND column_name = 'churn_date'
    ) THEN
        RAISE EXCEPTION 'A prohibited permanent churn or churn-date attribute exists';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'analytics'
          AND lower(column_name) IN ('revenue', 'mrr', 'arpu', 'ltv')
    ) THEN
        RAISE EXCEPTION 'An unsupported financial metric was created';
    END IF;

    IF to_regclass('staging.user_logs') IS NOT NULL
       OR to_regclass('staging.user_logs_v2') IS NOT NULL
       OR to_regclass('analytics.fact_user_activity_daily') IS NOT NULL
       OR to_regclass('analytics.fact_user_activity_monthly') IS NOT NULL
    THEN
        RAISE EXCEPTION 'User-log data or activity facts are unexpectedly present';
    END IF;

    RAISE NOTICE 'dim_user: % rows (% with metadata, % without)',
        dim_rows, with_metadata, without_metadata;
    RAISE NOTICE 'February churn: % true, % false', feb_churned, feb_not_churned;
    RAISE NOTICE 'March churn: % true, % false', mar_churned, mar_not_churned;
    RAISE NOTICE 'Transaction view: % original, % v2',
        original_transactions, v2_transactions;
    RAISE NOTICE 'Core analytics layer verification passed';
END $$;

ROLLBACK;
