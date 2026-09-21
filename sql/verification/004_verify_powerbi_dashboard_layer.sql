-- Read-only deterministic verification for the compact Power BI layer.

BEGIN TRANSACTION READ ONLY;

DO $$
DECLARE
    overview_rows BIGINT;
BEGIN
    IF to_regclass('analytics.v_powerbi_overview_kpis') IS NULL
       OR to_regclass('analytics.mv_powerbi_transaction_activity') IS NULL
       OR to_regclass('analytics.mv_powerbi_churn_transitions') IS NULL
       OR to_regclass('analytics.mv_powerbi_transaction_distributions') IS NULL
       OR to_regclass('analytics.mv_powerbi_churn_transaction_behavior') IS NULL
    THEN
        RAISE EXCEPTION 'One or more Power BI presentation objects are missing';
    END IF;

    IF (SELECT count(*) FROM analytics.mv_powerbi_transaction_activity) <> 28
       OR (SELECT count(*) FROM analytics.mv_powerbi_churn_transitions) <> 4
       OR (SELECT count(*) FROM analytics.mv_powerbi_transaction_distributions) <> 9
       OR (SELECT count(*) FROM analytics.mv_powerbi_churn_transaction_behavior) <> 4
    THEN
        RAISE EXCEPTION 'A compact Power BI object has an unexpected row count';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM analytics.mv_powerbi_transaction_activity
        WHERE period_grain = 'all_time' AND transaction_month IS NULL
          AND transaction_records = 22978755
          AND unique_transacting_users = 2426143
          AND auto_renew_records = 19481725
          AND cancellation_records = 891984
    ) OR (SELECT sum(transaction_records)
          FROM analytics.mv_powerbi_transaction_activity
          WHERE period_grain = 'month') <> 22978755
    THEN
        RAISE EXCEPTION 'Power BI transaction activity totals are incorrect';
    END IF;

    IF EXISTS (
        (SELECT transition, users, shared_users
         FROM analytics.mv_powerbi_churn_transitions
         EXCEPT
         SELECT * FROM (VALUES
             ('non_churn_to_non_churn'::TEXT, 824659::BIGINT, 881701::NUMERIC),
             ('non_churn_to_churn', 40721::BIGINT, 881701::NUMERIC),
             ('churn_to_non_churn', 5269::BIGINT, 881701::NUMERIC),
             ('churn_to_churn', 11052::BIGINT, 881701::NUMERIC)
         ) AS expected(transition, users, shared_users))
        UNION ALL
        (SELECT * FROM (VALUES
             ('non_churn_to_non_churn'::TEXT, 824659::BIGINT, 881701::NUMERIC),
             ('non_churn_to_churn', 40721::BIGINT, 881701::NUMERIC),
             ('churn_to_non_churn', 5269::BIGINT, 881701::NUMERIC),
             ('churn_to_churn', 11052::BIGINT, 881701::NUMERIC)
         ) AS expected(transition, users, shared_users)
         EXCEPT
         SELECT transition, users, shared_users
         FROM analytics.mv_powerbi_churn_transitions)
    ) THEN
        RAISE EXCEPTION 'Power BI churn transition values are incorrect';
    END IF;

    IF EXISTS (
        (SELECT distribution, category, records
         FROM analytics.mv_powerbi_transaction_distributions
         EXCEPT
         SELECT * FROM (VALUES
             ('payment_plan_days'::TEXT, '0'::TEXT, 872342::BIGINT),
             ('payment_plan_days', '01-29', 641357::BIGINT),
             ('payment_plan_days', '30', 20174288::BIGINT),
             ('payment_plan_days', '31', 766612::BIGINT),
             ('payment_plan_days', '032-365', 331371::BIGINT),
             ('payment_plan_days', 'over_365', 192785::BIGINT),
             ('price_relationship', 'equal', 21252049::BIGINT),
             ('price_relationship', 'paid_below_list', 867020::BIGINT),
             ('price_relationship', 'paid_above_list', 859686::BIGINT)
         ) AS expected(distribution, category, records))
        UNION ALL
        (SELECT * FROM (VALUES
             ('payment_plan_days'::TEXT, '0'::TEXT, 872342::BIGINT),
             ('payment_plan_days', '01-29', 641357::BIGINT),
             ('payment_plan_days', '30', 20174288::BIGINT),
             ('payment_plan_days', '31', 766612::BIGINT),
             ('payment_plan_days', '032-365', 331371::BIGINT),
             ('payment_plan_days', 'over_365', 192785::BIGINT),
             ('price_relationship', 'equal', 21252049::BIGINT),
             ('price_relationship', 'paid_below_list', 867020::BIGINT),
             ('price_relationship', 'paid_above_list', 859686::BIGINT)
         ) AS expected(distribution, category, records)
         EXCEPT
         SELECT distribution, category, records
         FROM analytics.mv_powerbi_transaction_distributions)
    ) THEN
        RAISE EXCEPTION 'Power BI transaction distributions are incorrect';
    END IF;

    IF EXISTS (
        (SELECT expiry_cohort_month, is_churn, cohort_users,
                users_with_transaction_records, transaction_records
         FROM analytics.mv_powerbi_churn_transaction_behavior
         EXCEPT
         SELECT * FROM (VALUES
             (DATE '2017-02-01', FALSE, 929460::BIGINT, 927455::BIGINT, 2731650::NUMERIC),
             (DATE '2017-02-01', TRUE, 63471::BIGINT, 54200::BIGINT, 128604::NUMERIC),
             (DATE '2017-03-01', FALSE, 883630::BIGINT, 882959::BIGINT, 2638319::NUMERIC),
             (DATE '2017-03-01', TRUE, 87330::BIGINT, 76749::BIGINT, 186419::NUMERIC)
         ) AS expected(expiry_cohort_month, is_churn, cohort_users,
                       users_with_transaction_records, transaction_records))
        UNION ALL
        (SELECT * FROM (VALUES
             (DATE '2017-02-01', FALSE, 929460::BIGINT, 927455::BIGINT, 2731650::NUMERIC),
             (DATE '2017-02-01', TRUE, 63471::BIGINT, 54200::BIGINT, 128604::NUMERIC),
             (DATE '2017-03-01', FALSE, 883630::BIGINT, 882959::BIGINT, 2638319::NUMERIC),
             (DATE '2017-03-01', TRUE, 87330::BIGINT, 76749::BIGINT, 186419::NUMERIC)
         ) AS expected(expiry_cohort_month, is_churn, cohort_users,
                       users_with_transaction_records, transaction_records)
         EXCEPT
         SELECT expiry_cohort_month, is_churn, cohort_users,
                users_with_transaction_records, transaction_records
         FROM analytics.mv_powerbi_churn_transaction_behavior)
    ) THEN
        RAISE EXCEPTION 'Power BI churn/transaction behavior values are incorrect';
    END IF;

    SELECT count(*) INTO overview_rows FROM analytics.v_powerbi_overview_kpis
    WHERE canonical_user_count = 7207283
      AND transaction_records = 22978755
      AND unique_transacting_users = 2426143
      AND round(100 * member_metadata_coverage_rate, 4) = 93.9255
      AND round(100 * feb_churn_rate, 4) = 6.3923
      AND round(100 * mar_churn_rate, 4) = 8.9942;
    IF overview_rows <> 1 THEN
        RAISE EXCEPTION 'Power BI overview KPI row is incorrect';
    END IF;

    IF (SELECT count(*) FROM raw.source_file) <> 7
       OR (SELECT count(*) FROM staging.members) <> 6769473
       OR (SELECT count(*) FROM staging.churn_labels) <> 1963891
       OR (SELECT count(*) FROM staging.transactions) <> 22978755
    THEN
        RAISE EXCEPTION 'Source or staging state changed';
    END IF;

    RAISE NOTICE 'Power BI dashboard layer verification passed';
END $$;

ROLLBACK;
