-- Rollback-safe behavioral verification for migration 002.
BEGIN;

DO $verification$
DECLARE
    test_source_key BIGINT;
    invalid_source_key CONSTANT BIGINT := -1;
    test_case RECORD;
    actual_count BIGINT;
BEGIN
    FOR test_case IN
        SELECT * FROM (VALUES
            ('members', 9), ('churn_labels', 6), ('transactions', 19)
        ) AS expected(table_name, column_count)
    LOOP
        IF to_regclass('staging.' || test_case.table_name) IS NULL THEN
            RAISE EXCEPTION 'Missing staging table: %', test_case.table_name;
        END IF;
        SELECT count(*) INTO actual_count
        FROM information_schema.columns
        WHERE table_schema = 'staging' AND table_name = test_case.table_name;
        IF actual_count <> test_case.column_count THEN
            RAISE EXCEPTION 'Unexpected column count for staging.%: %',
                test_case.table_name, actual_count;
        END IF;
    END LOOP;

    FOR test_case IN
        SELECT * FROM (VALUES
            ('members','source_file_key','bigint',''), ('members','source_row_number','bigint',''),
            ('members','msno','text',''), ('members','city_code','integer',''),
            ('members','bd_raw','integer',''), ('members','gender','text',''),
            ('members','registered_via_code','integer',''),
            ('members','registration_init_date','date',''),
            ('members','loaded_at','timestamp with time zone',''),
            ('churn_labels','source_file_key','bigint',''),
            ('churn_labels','source_row_number','bigint',''), ('churn_labels','msno','text',''),
            ('churn_labels','is_churn','boolean',''),
            ('churn_labels','expiry_cohort_month','date',''),
            ('churn_labels','loaded_at','timestamp with time zone',''),
            ('transactions','source_file_key','bigint',''),
            ('transactions','source_row_number','bigint',''), ('transactions','msno','text',''),
            ('transactions','payment_method_id','integer',''),
            ('transactions','payment_plan_days','integer',''),
            ('transactions','plan_list_price','integer',''),
            ('transactions','actual_amount_paid','integer',''),
            ('transactions','is_auto_renew','boolean',''),
            ('transactions','transaction_date','date',''),
            ('transactions','membership_expire_date','date',''),
            ('transactions','is_cancel','boolean',''),
            ('transactions','loaded_at','timestamp with time zone',''),
            ('transactions','price_difference','integer','ALWAYS'),
            ('transactions','price_relationship','text','ALWAYS'),
            ('transactions','expiry_delta_days','integer','ALWAYS'),
            ('transactions','has_negative_expiry_delta','boolean','ALWAYS'),
            ('transactions','has_zero_expiry_delta','boolean','ALWAYS'),
            ('transactions','has_long_expiry_delta','boolean','ALWAYS'),
            ('transactions','plan_expiry_relationship','text','ALWAYS')
        ) AS expected(table_name, column_name, data_type, is_generated)
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns c
            WHERE c.table_schema = 'staging'
              AND c.table_name = test_case.table_name
              AND c.column_name = test_case.column_name
              AND c.data_type = test_case.data_type
              AND c.is_generated = CASE
                  WHEN test_case.is_generated = '' THEN 'NEVER'
                  ELSE test_case.is_generated
              END
        ) THEN
            RAISE EXCEPTION 'Missing or incorrect column staging.%.%',
                test_case.table_name, test_case.column_name;
        END IF;
    END LOOP;
    RAISE NOTICE 'Object and column checks passed';

    IF EXISTS (SELECT 1 FROM raw.source_file WHERE relative_path = 'verification/002.csv') THEN
        RAISE EXCEPTION 'Reserved verification source already exists';
    END IF;
    INSERT INTO raw.source_file
        (file_name, relative_path, file_size_bytes, row_count, sha256)
    VALUES ('__verify_002__.csv', 'verification/002.csv', 202, 20, repeat('c', 64))
    RETURNING source_file_key INTO test_source_key;

    -- Members: valid/null gender and source anomalies must remain representable.
    INSERT INTO staging.members VALUES
        (test_source_key, 1, 'member-1', 1, 0, NULL, 1, DATE '2017-01-01', DEFAULT),
        (test_source_key, 2, 'member-2', 1, -5, 'male', 1, DATE '2017-01-01', DEFAULT),
        (test_source_key, 3, 'member-3', 1, 101, 'female', 1, DATE '2017-01-01', DEFAULT);
    BEGIN
        INSERT INTO staging.members VALUES
            (test_source_key, 0, 'bad-row', 1, 1, NULL, 1, DATE '2017-01-01', DEFAULT);
        RAISE EXCEPTION 'FAIL: members source_row_number 0 accepted';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        INSERT INTO staging.members VALUES
            (test_source_key, 1, 'duplicate', 1, 1, NULL, 1, DATE '2017-01-01', DEFAULT);
        RAISE EXCEPTION 'FAIL: duplicate members lineage accepted';
    EXCEPTION WHEN unique_violation THEN NULL; END;
    BEGIN
        INSERT INTO staging.members VALUES
            (invalid_source_key, 99, 'bad-fk', 1, 1, NULL, 1, DATE '2017-01-01', DEFAULT);
        RAISE EXCEPTION 'FAIL: members invalid source key accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL; END;
    BEGIN
        INSERT INTO staging.members VALUES
            (test_source_key, 4, '', 1, 1, NULL, 1, DATE '2017-01-01', DEFAULT);
        RAISE EXCEPTION 'FAIL: empty member msno accepted';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        INSERT INTO staging.members VALUES
            (test_source_key, 4, 'bad-gender', 1, 1, '', 1, DATE '2017-01-01', DEFAULT);
        RAISE EXCEPTION 'FAIL: empty gender accepted';
    EXCEPTION WHEN check_violation THEN NULL; END;
    RAISE NOTICE 'Member behavior passed';

    INSERT INTO staging.churn_labels VALUES
        (test_source_key, 1, 'churn-1', TRUE, DATE '2017-02-01', DEFAULT),
        (test_source_key, 2, 'churn-2', FALSE, DATE '2017-03-01', DEFAULT);
    BEGIN
        INSERT INTO staging.churn_labels VALUES
            (test_source_key, 0, 'bad-row', TRUE, DATE '2017-02-01', DEFAULT);
        RAISE EXCEPTION 'FAIL: churn source_row_number 0 accepted';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        INSERT INTO staging.churn_labels VALUES
            (test_source_key, 1, 'duplicate', TRUE, DATE '2017-02-01', DEFAULT);
        RAISE EXCEPTION 'FAIL: duplicate churn lineage accepted';
    EXCEPTION WHEN unique_violation THEN NULL; END;
    BEGIN
        INSERT INTO staging.churn_labels VALUES
            (invalid_source_key, 99, 'bad-fk', TRUE, DATE '2017-02-01', DEFAULT);
        RAISE EXCEPTION 'FAIL: churn invalid source key accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL; END;
    BEGIN
        INSERT INTO staging.churn_labels VALUES
            (test_source_key, 3, '', TRUE, DATE '2017-02-01', DEFAULT);
        RAISE EXCEPTION 'FAIL: empty churn msno accepted';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        INSERT INTO staging.churn_labels VALUES
            (test_source_key, 3, 'bad-cohort', TRUE, DATE '2017-02-15', DEFAULT);
        RAISE EXCEPTION 'FAIL: non-month-start cohort accepted';
    EXCEPTION WHEN check_violation THEN NULL; END;
    RAISE NOTICE 'Churn behavior passed';

    INSERT INTO staging.transactions
        (source_file_key, source_row_number, msno, payment_method_id,
         payment_plan_days, plan_list_price, actual_amount_paid, is_auto_renew,
         transaction_date, membership_expire_date, is_cancel)
    VALUES
        (test_source_key, 1, 'transaction-1', 1, 30, 149, 99, TRUE,
         DATE '2017-01-01', DATE '2017-01-31', FALSE),
        (test_source_key, 2, 'transaction-2', 1, 30, 99, 149, FALSE,
         DATE '2017-02-10', DATE '2017-02-01', TRUE),
        (test_source_key, 3, 'transaction-3', 1, 0, 0, 0, FALSE,
         DATE '2017-01-01', DATE '2019-01-02', FALSE),
        (test_source_key, 4, 'transaction-4', 1, 0, 1, 1, FALSE,
         DATE '2017-01-01', DATE '2017-01-01', FALSE);

    IF NOT EXISTS (
        SELECT 1 FROM staging.transactions
        WHERE source_file_key = test_source_key AND source_row_number = 1
          AND price_difference = 50 AND price_relationship = 'paid_below_list'
          AND expiry_delta_days = 30 AND NOT has_negative_expiry_delta
          AND NOT has_zero_expiry_delta AND NOT has_long_expiry_delta
          AND plan_expiry_relationship = 'equal' AND NOT is_cancel
    ) THEN RAISE EXCEPTION 'FAIL: transaction example 1 derived values'; END IF;
    IF NOT EXISTS (
        SELECT 1 FROM staging.transactions
        WHERE source_file_key = test_source_key AND source_row_number = 2
          AND price_difference = -50 AND price_relationship = 'paid_above_list'
          AND expiry_delta_days = -9 AND has_negative_expiry_delta
          AND NOT has_zero_expiry_delta AND NOT has_long_expiry_delta
          AND plan_expiry_relationship = 'expiry_shorter' AND is_cancel
    ) THEN RAISE EXCEPTION 'FAIL: transaction example 2 derived values'; END IF;
    IF NOT EXISTS (
        SELECT 1 FROM staging.transactions
        WHERE source_file_key = test_source_key AND source_row_number = 3
          AND payment_plan_days = 0 AND plan_list_price = 0 AND actual_amount_paid = 0
          AND price_difference = 0 AND price_relationship = 'equal'
          AND expiry_delta_days = 731 AND has_long_expiry_delta
          AND plan_expiry_relationship = 'expiry_longer'
    ) THEN RAISE EXCEPTION 'FAIL: long/zero transaction preservation'; END IF;
    IF NOT EXISTS (
        SELECT 1 FROM staging.transactions
        WHERE source_file_key = test_source_key AND source_row_number = 4
          AND expiry_delta_days = 0 AND has_zero_expiry_delta
          AND NOT has_negative_expiry_delta AND NOT has_long_expiry_delta
          AND plan_expiry_relationship = 'equal'
    ) THEN RAISE EXCEPTION 'FAIL: zero expiry-delta generated values'; END IF;

    BEGIN
        INSERT INTO staging.transactions
            (source_file_key, source_row_number, msno, payment_method_id,
             payment_plan_days, plan_list_price, actual_amount_paid, is_auto_renew,
             transaction_date, membership_expire_date, is_cancel)
        VALUES (test_source_key, 0, 'bad-row', 1, 1, 1, 1, FALSE,
                DATE '2017-01-01', DATE '2017-01-02', FALSE);
        RAISE EXCEPTION 'FAIL: transaction source_row_number 0 accepted';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        INSERT INTO staging.transactions
            (source_file_key, source_row_number, msno, payment_method_id,
             payment_plan_days, plan_list_price, actual_amount_paid, is_auto_renew,
             transaction_date, membership_expire_date, is_cancel)
        VALUES (test_source_key, 1, 'duplicate', 1, 1, 1, 1, FALSE,
                DATE '2017-01-01', DATE '2017-01-02', FALSE);
        RAISE EXCEPTION 'FAIL: duplicate transaction lineage accepted';
    EXCEPTION WHEN unique_violation THEN NULL; END;
    BEGIN
        INSERT INTO staging.transactions
            (source_file_key, source_row_number, msno, payment_method_id,
             payment_plan_days, plan_list_price, actual_amount_paid, is_auto_renew,
             transaction_date, membership_expire_date, is_cancel)
        VALUES (invalid_source_key, 99, 'bad-fk', 1, 1, 1, 1, FALSE,
                DATE '2017-01-01', DATE '2017-01-02', FALSE);
        RAISE EXCEPTION 'FAIL: transaction invalid source key accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL; END;
    BEGIN
        INSERT INTO staging.transactions
            (source_file_key, source_row_number, msno, payment_method_id,
             payment_plan_days, plan_list_price, actual_amount_paid, is_auto_renew,
             transaction_date, membership_expire_date, is_cancel)
        VALUES (test_source_key, 5, '', 1, 1, 1, 1, FALSE,
                DATE '2017-01-01', DATE '2017-01-02', FALSE);
        RAISE EXCEPTION 'FAIL: empty transaction msno accepted';
    EXCEPTION WHEN check_violation THEN NULL; END;
    RAISE NOTICE 'Transaction behavior and generated-column checks passed';
    RAISE NOTICE 'Core staging verification passed; rolling back test rows';
END;
$verification$;

ROLLBACK;
