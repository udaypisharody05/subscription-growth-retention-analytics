-- First DDL milestone: schemas and source-file lineage only.
-- Raw CSV contents remain on disk under data/raw/; nothing is loaded here.
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS analytics;

-- One row represents one registered immutable source-file version.
-- A nullable hash permits provisional registration, not proof of file identity.
-- IF NOT EXISTS supports reruns but does not reconcile an existing definition.
CREATE TABLE IF NOT EXISTS raw.source_file (
    source_file_key BIGINT GENERATED ALWAYS AS IDENTITY,
    file_name TEXT NOT NULL,
    -- Repository-relative path, e.g. data/raw/transactions.csv; no local drive paths.
    relative_path TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    row_count BIGINT,
    -- Filesystem metadata only; not authoritative source chronology or identity.
    file_modified_at TIMESTAMPTZ,
    sha256 CHAR(64),
    -- Registration metadata, not a source-event timestamp.
    registered_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,

    CONSTRAINT source_file_pkey PRIMARY KEY (source_file_key),
    CONSTRAINT source_file_file_name_nonempty CHECK (file_name <> ''),
    CONSTRAINT source_file_relative_path_nonempty CHECK (relative_path <> ''),
    CONSTRAINT source_file_size_nonnegative CHECK (file_size_bytes >= 0),
    CONSTRAINT source_file_row_count_nonnegative
        CHECK (row_count IS NULL OR row_count >= 0),
    CONSTRAINT source_file_sha256_format
        CHECK (sha256 IS NULL OR sha256::TEXT ~ '^[0-9a-f]{64}$'),
    CONSTRAINT source_file_version_unique
        UNIQUE (relative_path, file_size_bytes, sha256)
);

-- Normal UNIQUE rejects repeated path/size/hash triples when the hash is known.
-- NULL hashes remain distinct under that constraint; guard provisional entries
-- separately without claiming that equal path/size proves identical contents.
CREATE UNIQUE INDEX IF NOT EXISTS source_file_unhashed_path_size_unique
    ON raw.source_file (relative_path, file_size_bytes)
    WHERE sha256 IS NULL;

-- A hashed and an unhashed registration may coexist for the same path/size.
-- No source-file records, other tables, or data loads are introduced here.
