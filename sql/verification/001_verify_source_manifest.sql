-- Run this entire script as a standalone transaction, not inside other work.
-- All test rows are rolled back. Identity sequence values may still advance:
-- PostgreSQL does not roll back sequence allocations.
-- An unexpected failure aborts the transaction; no test rows can be committed.
BEGIN;

DO $verification$
DECLARE
    schema_name TEXT;
    test_file CONSTANT TEXT := '__constraint_test__.csv';
    test_path CONSTANT TEXT := 'data/raw/__constraint_test__.csv';
    actual_constraint TEXT;
    test_case RECORD;
BEGIN
    FOREACH schema_name IN ARRAY ARRAY['raw', 'staging', 'analytics']
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname = schema_name
        ) THEN
            RAISE EXCEPTION 'Required schema is missing: %', schema_name;
        END IF;
    END LOOP;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_class AS c
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'raw'
          AND c.relname = 'source_file'
          AND c.relkind IN ('r', 'p')
    ) THEN
        RAISE EXCEPTION 'Required table raw.source_file is missing';
    END IF;
    RAISE NOTICE 'Schema and table checks passed';

    -- Do not mistake an existing registration for a successful test insert.
    -- Refuse to use reserved test paths if either is already registered.
    IF EXISTS (
        SELECT 1 FROM raw.source_file
        WHERE relative_path IN (test_path, test_path || '.nullable')
    ) THEN
        RAISE EXCEPTION 'Reserved verification path already exists; no test performed';
    END IF;

    INSERT INTO raw.source_file
        (file_name, relative_path, file_size_bytes, row_count, sha256)
    VALUES (test_file, test_path, 123, 10, NULL);

    BEGIN
        INSERT INTO raw.source_file
            (file_name, relative_path, file_size_bytes, row_count, sha256)
        VALUES (test_file, test_path, 123, 10, NULL);
        -- This exception is not a unique_violation, so it cannot be swallowed.
        RAISE EXCEPTION 'FAIL: duplicate unhashed registration was accepted';
    EXCEPTION
        WHEN unique_violation THEN
            GET STACKED DIAGNOSTICS actual_constraint = CONSTRAINT_NAME;
            IF actual_constraint IS DISTINCT FROM 'source_file_unhashed_path_size_unique' THEN
                RAISE EXCEPTION 'FAIL: unexpected uniqueness failure: %', actual_constraint;
            END IF;
    END;
    RAISE NOTICE 'Unhashed uniqueness passed';

    -- Also verifies that a hashed and an unhashed entry may share path/size.
    INSERT INTO raw.source_file
        (file_name, relative_path, file_size_bytes, row_count, sha256)
    VALUES (test_file, test_path, 123, 10, repeat('a', 64));

    BEGIN
        INSERT INTO raw.source_file
            (file_name, relative_path, file_size_bytes, row_count, sha256)
        VALUES (test_file, test_path, 123, 10, repeat('a', 64));
        RAISE EXCEPTION 'FAIL: duplicate hashed registration was accepted';
    EXCEPTION
        WHEN unique_violation THEN
            GET STACKED DIAGNOSTICS actual_constraint = CONSTRAINT_NAME;
            IF actual_constraint IS DISTINCT FROM 'source_file_version_unique' THEN
                RAISE EXCEPTION 'FAIL: unexpected uniqueness failure: %', actual_constraint;
            END IF;
    END;

    -- A different valid lowercase hash for the same path/size must succeed.
    INSERT INTO raw.source_file
        (file_name, relative_path, file_size_bytes, row_count, sha256)
    VALUES (test_file, test_path, 123, 10, repeat('b', 64));
    RAISE NOTICE 'Hashed uniqueness and distinct lowercase hashes passed';

    -- Each fixture violates exactly one intended check. Size 124 avoids the
    -- successful path/size registrations above for all non-size test cases.
    FOR test_case IN
        SELECT * FROM (VALUES
            ('empty file_name', '', test_path, 124::BIGINT, 10::BIGINT, NULL::TEXT,
             'source_file_file_name_nonempty'),
            ('empty relative_path', test_file, '', 124::BIGINT, 10::BIGINT, NULL::TEXT,
             'source_file_relative_path_nonempty'),
            ('negative file_size_bytes', test_file, test_path, -1::BIGINT, 10::BIGINT, NULL::TEXT,
             'source_file_size_nonnegative'),
            ('negative row_count', test_file, test_path, 124::BIGINT, -1::BIGINT, NULL::TEXT,
             'source_file_row_count_nonnegative'),
            ('malformed sha256', test_file, test_path, 124::BIGINT, 10::BIGINT, 'not-a-hash',
             'source_file_sha256_format'),
            ('uppercase sha256', test_file, test_path, 124::BIGINT, 10::BIGINT, repeat('A', 64),
             'source_file_sha256_format')
        ) AS cases(test_name, file_name, relative_path, file_size_bytes,
                   row_count, sha256, expected_constraint)
    LOOP
        BEGIN
            INSERT INTO raw.source_file
                (file_name, relative_path, file_size_bytes, row_count, sha256)
            VALUES (test_case.file_name, test_case.relative_path,
                    test_case.file_size_bytes, test_case.row_count, test_case.sha256);
            RAISE EXCEPTION 'FAIL: invalid insert was accepted: %', test_case.test_name;
        EXCEPTION
            WHEN check_violation THEN
                GET STACKED DIAGNOSTICS actual_constraint = CONSTRAINT_NAME;
                IF actual_constraint IS DISTINCT FROM test_case.expected_constraint THEN
                    RAISE EXCEPTION 'FAIL: % raised unexpected check: %',
                        test_case.test_name, actual_constraint;
                END IF;
        END;
    END LOOP;
    RAISE NOTICE 'Check constraints passed';

    INSERT INTO raw.source_file
        (file_name, relative_path, file_size_bytes, row_count,
         file_modified_at, sha256, notes)
    VALUES (test_file, test_path || '.nullable', 123, NULL, NULL, NULL, NULL);

    IF NOT EXISTS (
        SELECT 1 FROM raw.source_file
        WHERE relative_path = test_path || '.nullable'
          AND row_count IS NULL
          AND file_modified_at IS NULL
          AND sha256 IS NULL
          AND notes IS NULL
    ) THEN
        RAISE EXCEPTION 'FAIL: intended nullable fields did not remain NULL';
    END IF;
    RAISE NOTICE 'Nullable fields passed';
    RAISE NOTICE 'Source manifest verification passed; rolling back all test rows';
END;
$verification$;

ROLLBACK;
