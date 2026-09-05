-- Core typed staging tables. This migration creates structure only and loads no CSV data.
-- Each table preserves one source row through its immutable file and 1-based data-row lineage.

CREATE TABLE IF NOT EXISTS staging.members (
    source_file_key BIGINT NOT NULL,
    source_row_number BIGINT NOT NULL,
    msno TEXT NOT NULL,
    city_code INTEGER NOT NULL,
    bd_raw INTEGER NOT NULL,
    gender TEXT,
    registered_via_code INTEGER NOT NULL,
    registration_init_date DATE NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT members_pkey PRIMARY KEY (source_file_key, source_row_number),
    CONSTRAINT members_source_file_fk FOREIGN KEY (source_file_key)
        REFERENCES raw.source_file (source_file_key),
    CONSTRAINT members_source_row_positive CHECK (source_row_number > 0),
    CONSTRAINT members_msno_nonempty CHECK (msno <> ''),
    CONSTRAINT members_gender_nonempty CHECK (gender IS NULL OR gender <> '')
);

COMMENT ON TABLE staging.members IS
    'Typed member-enrichment source rows with file and 1-based CSV data-row lineage.';
COMMENT ON COLUMN staging.members.bd_raw IS
    'Unmodified source demographic value; analytical age cleaning occurs later.';
COMMENT ON COLUMN staging.members.loaded_at IS
    'Ingestion metadata timestamp, not a source-event timestamp.';

CREATE TABLE IF NOT EXISTS staging.churn_labels (
    source_file_key BIGINT NOT NULL,
    source_row_number BIGINT NOT NULL,
    msno TEXT NOT NULL,
    is_churn BOOLEAN NOT NULL,
    expiry_cohort_month DATE NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT churn_labels_pkey PRIMARY KEY (source_file_key, source_row_number),
    CONSTRAINT churn_labels_source_file_fk FOREIGN KEY (source_file_key)
        REFERENCES raw.source_file (source_file_key),
    CONSTRAINT churn_labels_source_row_positive CHECK (source_row_number > 0),
    CONSTRAINT churn_labels_msno_nonempty CHECK (msno <> ''),
    CONSTRAINT churn_labels_cohort_month_start
        CHECK (EXTRACT(DAY FROM expiry_cohort_month) = 1)
);

COMMENT ON TABLE staging.churn_labels IS
    'Time-dependent churn-label source observations with expiry-cohort and source-row lineage.';
COMMENT ON COLUMN staging.churn_labels.expiry_cohort_month IS
    'First-day month anchor for the expiry cohort, not an exact expiry or churn event date.';
COMMENT ON COLUMN staging.churn_labels.loaded_at IS
    'Ingestion metadata timestamp, not a source-event timestamp.';

CREATE TABLE IF NOT EXISTS staging.transactions (
    source_file_key BIGINT NOT NULL,
    source_row_number BIGINT NOT NULL,
    msno TEXT NOT NULL,
    payment_method_id INTEGER NOT NULL,
    payment_plan_days INTEGER NOT NULL,
    plan_list_price INTEGER NOT NULL,
    actual_amount_paid INTEGER NOT NULL,
    is_auto_renew BOOLEAN NOT NULL,
    transaction_date DATE NOT NULL,
    membership_expire_date DATE NOT NULL,
    is_cancel BOOLEAN NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    price_difference INTEGER GENERATED ALWAYS AS
        (plan_list_price - actual_amount_paid) STORED,
    price_relationship TEXT GENERATED ALWAYS AS (
        CASE
            WHEN actual_amount_paid = plan_list_price THEN 'equal'
            WHEN actual_amount_paid < plan_list_price THEN 'paid_below_list'
            ELSE 'paid_above_list'
        END
    ) STORED,
    expiry_delta_days INTEGER GENERATED ALWAYS AS
        (membership_expire_date - transaction_date) STORED,
    has_negative_expiry_delta BOOLEAN GENERATED ALWAYS AS
        ((membership_expire_date - transaction_date) < 0) STORED,
    has_zero_expiry_delta BOOLEAN GENERATED ALWAYS AS
        ((membership_expire_date - transaction_date) = 0) STORED,
    has_long_expiry_delta BOOLEAN GENERATED ALWAYS AS
        ((membership_expire_date - transaction_date) > 730) STORED,
    plan_expiry_relationship TEXT GENERATED ALWAYS AS (
        CASE
            WHEN membership_expire_date - transaction_date = payment_plan_days THEN 'equal'
            WHEN membership_expire_date - transaction_date < payment_plan_days THEN 'expiry_shorter'
            ELSE 'expiry_longer'
        END
    ) STORED,

    CONSTRAINT transactions_pkey PRIMARY KEY (source_file_key, source_row_number),
    CONSTRAINT transactions_source_file_fk FOREIGN KEY (source_file_key)
        REFERENCES raw.source_file (source_file_key),
    CONSTRAINT transactions_source_row_positive CHECK (source_row_number > 0),
    CONSTRAINT transactions_msno_nonempty CHECK (msno <> '')
);

COMMENT ON TABLE staging.transactions IS
    'Typed transaction source rows preserved without customer/date deduplication.';
COMMENT ON COLUMN staging.transactions.price_difference IS
    'Derived list-minus-paid analytical difference; not an official discount.';
COMMENT ON COLUMN staging.transactions.has_long_expiry_delta IS
    'True above 730 days: a project analytical convention, not an official KKBox invalidity rule.';
COMMENT ON COLUMN staging.transactions.plan_expiry_relationship IS
    'Descriptive comparison only; shorter or longer is not automatically an error.';
COMMENT ON COLUMN staging.transactions.is_cancel IS
    'Source cancellation flag; cancellation is not churn.';
COMMENT ON COLUMN staging.transactions.loaded_at IS
    'Ingestion metadata timestamp, not a source-event timestamp.';

-- Only primary-key indexes are created. Analytical indexes await load and query-plan evidence.
-- No full user-log staging table is created; activity will be handled by bounded aggregation.
