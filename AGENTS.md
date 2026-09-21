# Subscription Product Growth & Retention Analytics

## Project boundaries

- Use PostgreSQL database `subscription_growth_retention` and its `raw`, `staging`, and `analytics` schemas.
- Treat every CSV under `data/raw/` as immutable local source data. Never edit or commit raw data.
- Keep the fingerprint cache under `data/processed/` local and ignored. Never commit caches, credentials, or temporary files.
- Never fabricate source data, metrics, verification results, or analytical findings.

## Ingestion and lineage

- Resolve each source version through its registered relative path, byte size, and SHA-256 fingerprint in `raw.source_file`.
- Preserve `source_file_key` and `source_row_number` lineage throughout staging and downstream processing.
- Prefer PostgreSQL bulk `COPY`/`\copy` for large relational loads. Standard-library Python plus `psql` is the preferred ingestion approach.
- Keep Python memory bounded and stream large files. Do not use pandas for large ingestion tasks unless it is explicitly needed and memory safety is demonstrated.
- Do not bulk-load the full 410M+ row user-log dataset into PostgreSQL. Use memory-bounded streaming aggregation when user activity work begins.
- Never expose PostgreSQL credentials. Do not inspect or commit `pgpass.conf`.

## Domain and modeling rules

- `members_v3.csv` is optional customer enrichment, not the customer universe. Use `LEFT JOIN` semantics where member metadata may be absent.
- Churn is a time-dependent observation, not a permanent user attribute. Do not store churn on `dim_user`.
- Assign `train.csv` to expiry cohort `2017-02-01` and `train_v2.csv` to expiry cohort `2017-03-01`; the outcome window is the following 30 days.
- `is_cancel` is not equivalent to churn.
- Preserve unusual transaction values for traceability rather than deleting them. Do not deduplicate transactions on `msno` and date.
- The greater-than-730-day membership-expiry flag is a project convention for investigation, not an official declaration of invalidity.
- Do not define revenue, MRR, ARPU, or LTV until the methodology is explicitly justified against the source semantics.

## Validation and delivery

- Run automated, deterministic verification for every milestone. Once it passes, avoid redundant repeated checks unless inputs or implementation changed.
- Commit only validated milestone files. Never commit raw data, derived caches, credentials, or temporary artifacts.

## Current completed state

- `raw.source_file`: 7 registered source files.
- `staging.members`: 6,769,473 rows loaded.
- `staging.churn_labels`: 1,963,891 rows loaded.
- `staging.transactions`: 22,978,755 rows loaded.
- The core V1 user, churn, and transaction analytics layer is implemented.
- User-activity processing and its daily/monthly facts remain future work.
