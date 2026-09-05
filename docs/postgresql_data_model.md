# PostgreSQL Analytical Data Model

This document combines the proposed analytical design with implementation notes for completed database milestones. Migration 002 implements only the core staging structures described below; the analytical dimensions, facts, data loads, and ingestion jobs remain future work. Proposed grains and processing rules are design choices, not additional claims about the source data.

## 1. Design Principles

- Preserve the immutable raw source files and their provenance. Cleaning must not overwrite the originals.
- Separate source preservation, typed/clean staging, and the analytical dimensional model.
- Define the grain of every table explicitly. Do not infer source uniqueness from convenient customer/date combinations.
- Retain source lineage so analytical records can be traced to their source file and, where applicable, source record.
- Build customer identity independently of member metadata. Missing demographic or registration information must remain nullable and must not remove otherwise valid facts.
- Represent churn as a time-dependent observation, not a permanent customer attribute.
- Preserve both transaction files. Zero exact full-row overlap does not justify collapsing records that share a customer/date key.
- Treat the activity files as a storage constraint: stream and aggregate them without retaining redundant copies of all 410+ million source rows in multiple database layers.
- Keep the design useful for growth, churn, retention/cohort, transaction/revenue, engagement, and Power BI analysis without inventing business definitions that have not been verified.

## 2. Data Layers

The three logical PostgreSQL schemas are `raw`, `staging`, and `analytics`. They do not require three physical copies of every source dataset.

| Layer | Responsibility | Proposed storage approach |
| --- | --- | --- |
| Raw source files on disk | Immutable evidence for reprocessing and audit | Preserve the seven CSVs outside PostgreSQL. These are source files, not PostgreSQL tables. |
| `raw` schema | Register source-file identity and provenance | A lightweight `raw.source_file` manifest identifies each immutable file version. Full raw activity rows are not required in PostgreSQL. |
| `staging` schema | Parse, type, validate, and prepare source data | Stage members, transactions, and churn labels with lineage. Use bounded activity partial aggregates rather than a permanent raw activity copy. |
| `analytics` schema | Expose dimensions and facts at declared grains | Persist the customer/date dimensions, transaction and churn facts, daily activity aggregates, and a smaller monthly activity fact. |

The manifest should conceptually record a source-file key, filename, file-version identity, and processing provenance. Facts can carry the readable `source_file` alongside a reference to this manifest. No source row content belongs in the manifest.

Typed/clean staging means that proposed types and validation rules are applied deliberately, with exceptions made visible. It does not authorize silent deletion, arbitrary correction, or undocumented deduplication. Specific cleaning policies remain open until validated.

For activity, the intended path is immutable CSVs, bounded streaming partial aggregation, and a consolidated daily analytical fact. Partial staging data is temporary working data and should be released after successful consolidation and validation. A persistent PostgreSQL raw log table plus a full staging log table plus a full analytical log copy is not the proposed design.

### Implemented core staging schema

Migration 002 creates three currently empty typed staging tables. Data loading is a later milestone.

| Implemented table | Physical grain and treatment |
| --- | --- |
| `staging.members` | One `members_v3.csv` source row, retained as typed member enrichment with file and 1-based data-row lineage. Raw `bd` values remain in `bd_raw`; analytical age cleaning occurs later. |
| `staging.churn_labels` | One time-dependent labeled-user source observation for an expiry cohort, with lineage. The cohort uses a first-of-month anchor; no exact churn date is invented. |
| `staging.transactions` | One preserved transaction source row with lineage and no customer/date deduplication. Deterministic stored generated columns describe price, transaction-to-expiry, and plan-to-expiry relationships. |

The transaction long-expiry flag uses `expiry_delta_days > 730`. This is a project analytical convention, not an official KKBox invalidity rule. The generated relationship fields preserve and expose unusual values rather than rejecting them. No full raw user-log staging table exists by design; activity will be processed later through bounded aggregation.

## 3. Customer Identity Strategy

The customer universe consists of all distinct non-empty `msno` values across the relevant sources, including members, both transaction files, both label files, and both activity files. Each identity receives one stable `user_key`; enrichment from `members_v3.csv` is optional.

Conceptually: all source identities -> canonical customer identity -> optional member enrichment.

`members_v3.csv` has 6,769,473 rows and distinct users, with no duplicate or empty `msno`, but it is not a complete customer master:

| Source | Distinct-user member coverage |
| --- | ---: |
| transactions.csv | 81.6966% |
| transactions_v2.csv | 90.0074% |
| train.csv | 88.3406% |
| train_v2.csv | 88.6717% |
| user_logs.csv | 96.7487% |
| user_logs_v2.csv | 99.9964% |

Proposed `analytics.dim_user` grain: one canonical source customer identity.

| Conceptual field | Meaning |
| --- | --- |
| `user_key` | Stable surrogate key used by facts |
| `msno` | Unique natural/anonymized source identifier |
| `has_member_metadata` | Whether a corresponding member record exists |
| `city` | Nullable member attribute |
| `bd` | Nullable source demographic value; interpretation and quality rules still require validation |
| `gender` | Nullable member attribute |
| `registered_via` | Nullable registration attribute |
| `registration_init_time` | Nullable registration information from the member source, typed after validation |

The identity record must exist even when all optional member attributes are unavailable. Enrichment uses LEFT JOIN semantics against the member source, never an inclusion filter. A member-only identity may also exist without facts; inclusion in the dimension alone does not establish paid-subscriber status.

Do not include `is_churn` or a current churn status inferred from the training files. Those labels refer to expiry-cohort observations and can change for the same customer. The available member attributes also do not establish a historical demographic change timeline; none is invented here.

The efficient construction of the canonical identity universe remains an implementation question. The design requires one identity per `msno`, not simultaneous in-memory sets for every source.

## 4. Transaction Model

Proposed table: `analytics.fact_transaction`.

Grain: one preserved KKBox transaction source record, not one customer/day and not an assumed unique business payment.

Conceptual fields:

- `transaction_key`: surrogate key for the preserved source record.
- `user_key`: canonical customer identity.
- `transaction_date`.
- `membership_expire_date`.
- `payment_method_id`.
- `payment_plan_days`.
- `plan_list_price`.
- `actual_amount_paid`.
- `is_auto_renew`.
- `is_cancel`.
- `source_file`: readable source filename.
- `source_file_key`: immutable file-version lineage.
- `source_row_number`: CSV data-record ordinal within that file version, excluding the header; not necessarily a physical text-line number.

The file-version key plus source record ordinal provides an ingestion identity for avoiding accidental reloads of the same source record. It is not a business deduplication rule.

Preserve all 21,547,746 records from `transactions.csv` and all 1,431,009 records from `transactions_v2.csv`, subject to explicit validation handling rather than silent removal. The original covers 2015-01-01 through 2017-02-28. The v2 file contains historical-dated records as well as March 2017 records, which account for most of its rows.

Verified exact full-row overlap between the files is zero. V2 is not a simple duplicate append, and neither file should replace the other. Do not deduplicate on `(msno, transaction_date)` or discard historical-dated v2 records merely because their dates overlap the original file.

`is_cancel` is a cancellation indicator, not a churn label. Preserve transaction measures for analysis, but do not assume that summing every preserved `actual_amount_paid` value already defines net revenue or that every source record is an independent payment. Monetary interpretation and logical transaction overlap require appropriate validation before business measures are finalized.

## 5. Churn Observation Model

Proposed table: `analytics.fact_churn_observation`.

Grain: one customer + expiry cohort observation.

Conceptual fields:

- `churn_observation_key`.
- `user_key`.
- `expiry_cohort_month`.
- `is_churn`.
- `label_source`.

Source lineage can additionally retain the source-file key and source record ordinal in staging.

| Label source | `expiry_cohort_month` | Interpretation |
| --- | --- | --- |
| train.csv | 2017-02-01 | February 2017 membership-expiry cohort; renewal/churn evaluated over the following 30 days |
| train_v2.csv | 2017-03-01 | March 2017 membership-expiry cohort; renewal/churn evaluated over the following 30 days |

The first day of the month is a cohort anchor, not an exact expiration or churn event date. The actual evaluation window follows the relevant membership expiration and can extend into the following month. Exact churn event dates are unavailable.

The files contain 992,931 and 970,960 users respectively. Among 881,701 shared users, 45,990 (5.22%) change labels: 40,721 transition from 0 to 1 and 5,269 from 1 to 0. Therefore, `is_churn` must NOT be stored as a permanent `dim_user` attribute.

Different cohorts are separate observations, not competing versions of one timeless label. If a future load presents conflicting labels for the same customer/cohort, it must be surfaced for resolution rather than silently overwriting the observation or adding `label_source` to disguise a grain conflict.

## 6. Activity Model

The immutable activity CSVs remain the raw source:

- `user_logs.csv`: 392,106,543 rows, 5,234,111 distinct users, covering 2015-01-01 through 2017-02-28.
- `user_logs_v2.csv`: 18,396,362 rows, 1,103,894 distinct users, covering March 2017.

The verified date ranges do not overlap. Nevertheless, `(msno, date)` uniqueness within a source is not assumed.

### Daily analytical fact

Proposed table: `analytics.fact_user_activity_daily`.

Grain: one canonical user + activity date, created by explicit aggregation across all contributing source records.

Conceptual fields:

- `user_key`.
- `activity_date`.
- `num_25`, `num_50`, `num_75`, `num_985`, `num_100`.
- `num_unq`.
- `total_secs`.

Useful aggregate lineage fields are `source_file` and `source_record_count`. The currently non-overlapping source date ranges allow a daily row to identify its contributing activity file. If future files overlap, lineage must represent all contributing sources rather than arbitrarily selecting one. A 410-million-row lineage bridge is not required for this design.

| Source measure | Proposed consolidation treatment | Semantic limitation |
| --- | --- | --- |
| `num_25`, `num_50`, `num_75`, `num_985`, `num_100` | Sum each count separately across contributing records | Summation is valid for additive contributions. Repeated copies or overlapping snapshots would inflate results; that distinction must be checked before accepting the consolidation rule. Do not yet infer that the five fields can be combined into a unique play count. |
| `total_secs` | Sum contributing duration values | Appropriate for additive listening contributions, not repeated copies of the same contribution. Validate source values and duplicate behavior. |
| `num_unq` | Preserve the sum as an aggregated source metric, with explicit labeling | If multiple records contribute to a user/day, the sum is not proven to be the number of distinct songs that day. Song overlap cannot be resolved from these aggregate columns alone. |

Grouping multiple source records by user/date creates the desired daily grain; it is not proof that those source records are duplicates. In particular, summation must not be described as exact deduplication. The treatment of overlapping or repeated source contributions remains a validation gate before SQL/ETL implementation.

Use bounded streaming batches and partitioned, disk-backed partial aggregation rather than one dictionary containing every user/date across the entire dataset. Partial aggregates for a user/date must be merged across batches before a daily row is finalized; source ordering or contiguity must not be assumed.

Monthly date partitions are a proposed physical organization for the large daily fact, subject to capacity and query checks. Load and validate bounded partitions, release temporary partials after consolidation, and retain the CSVs for reproducibility. Daily aggregation may provide little row-count reduction if the source is already user/date-unique, so storage planning must not assume a large reduction.

### Monthly Power BI fact

Proposed table: `analytics.fact_user_activity_monthly`.

Grain: one user + activity month, with the month represented by its first day.

| Conceptual measure | Proposed meaning |
| --- | --- |
| `active_days` | Requires an agreed activity criterion. Counting dates with a source record is a possible operational definition, but must be labeled as observed activity days and must not silently imply positive listening. |
| Source count totals | Monthly sums of each daily count field, retaining separate categories |
| `total_plays` / song completion counts | Define only after the source count-category meanings and any overlap between categories are confirmed; do not invent a combined play formula now |
| `total_unique_song_count` | An explicitly labeled sum of the daily aggregated `num_unq` source metric, NOT globally unique monthly songs |
| `total_listening_seconds` | Sum of validated daily `total_secs` contributions |

Summing daily `num_unq` cannot identify songs that recur across days. If daily records themselves combine multiple source rows, that additional within-day limitation also carries forward. No true monthly distinct-song count is claimed.

The monthly fact is an intentional coarser-grained aggregate for routine Power BI analysis, not another copy of raw logs. Use it for the default engagement reporting surface; retain the daily fact for analyses that genuinely require daily detail. Do not import all 410+ million raw activity rows into a default dashboard model.

## 7. Date Dimension

Proposed table: `analytics.dim_date`.

Grain: one calendar date. Conceptual attributes include a date key, calendar date, year, month, month-start date, and day attributes useful for grouping and sorting.

The dimension provides consistent calendar slicing for transaction trends, activity trends, cohort comparisons, and Power BI. It can play distinct roles for transaction date, membership expiry date, activity date, expiry cohort month, and activity month.

The cohort/month roles use month-start anchors; they do not turn those anchors into actual events. Suspicious expiry values must be retained for investigation, and their treatment in analytical date relationships must follow the eventual validation policy rather than an invented replacement date.

## 8. Relationships

| Dimension | Fact | Conceptual relationship |
| --- | --- | --- |
| `analytics.dim_user` | `analytics.fact_transaction` | One user to many preserved transaction source records |
| `analytics.dim_user` | `analytics.fact_churn_observation` | One user to many expiry-cohort observations |
| `analytics.dim_user` | `analytics.fact_user_activity_daily` | One user to many daily activity rows |
| `analytics.dim_user` | `analytics.fact_user_activity_monthly` | One user to many monthly activity rows |
| `analytics.dim_date` | Transaction fact | One date to many facts through the transaction-date or expiry-date role |
| `analytics.dim_date` | Daily activity fact | One date to many daily activity rows |
| `analytics.dim_date` | Churn observation and monthly activity facts | One month-start anchor to many cohort/month observations |

Canonical identities are resolved before analytical facts reference `user_key`. The lack of a member record must not produce a missing canonical user or remove the fact.

Use LEFT JOIN semantics for optional member enrichment. Keep date roles explicit in Power BI so expiry and transaction dates are not confused. Avoid direct fact-to-fact joins at incompatible grains that multiply transaction, activity, or cohort rows; compare appropriately aggregated measures through shared dimensions.

## 9. Proposed Analytical Tables

| Table | Grain | Purpose |
| --- | --- | --- |
| `analytics.dim_user` | One distinct canonical `msno` | Shared customer identity with optional member enrichment |
| `analytics.dim_date` | One calendar date | Consistent date and month-anchor analysis |
| `analytics.fact_transaction` | One preserved transaction source record | Source-aware transaction and validated revenue analysis |
| `analytics.fact_churn_observation` | One user + expiry cohort month | Time-dependent churn outcomes |
| `analytics.fact_user_activity_daily` | One user + activity date after explicit aggregation | Daily engagement analysis |
| `analytics.fact_user_activity_monthly` | One user + activity month | Smaller Power BI-oriented engagement aggregates |

Minimal supporting tables:

| Table | Grain | Purpose |
| --- | --- | --- |
| `raw.source_file` | One immutable source-file version | Source identity and processing provenance without raw activity duplication |
| `staging.members` | One member source record | Typed member enrichment and quality checks |
| `staging.transactions` | One transaction source record, preserving file lineage | Typed preparation of both transaction files without customer/date deduplication |
| `staging.churn_labels` | One label source record | Label validation and verified expiry-cohort mapping |
| `staging.user_activity_daily_partial` | One user/date partial aggregate per processing batch and source | Bounded temporary working data to consolidate into the daily fact |

There is no requirement for permanent PostgreSQL raw or staging copies of every activity source row. Temporary activity partials are not a second permanent fact layer.

## 10. Key Modeling Decisions

1. `members_v3` is enrichment, not the customer universe.
2. Churn is a time-dependent observation tied to an expiry cohort.
3. Both transaction files are preserved with source lineage.
4. `is_cancel` is not churn.
5. Activity is streamed and explicitly aggregated rather than redundantly duplicated across database layers.
6. Missing member metadata must not remove otherwise valid facts.
7. An exact churn event date is unavailable.
8. Raw user/date uniqueness is not assumed; analytical daily uniqueness is created by an explicit aggregation process.

## 11. Open Questions Before SQL Implementation

- What validation and interpretation rules are appropriate for member demographics, especially `bd`, and other nullable member attributes?
- How should suspicious membership expiry dates such as 1970-01-01 and 2036-10-15 be represented in analytical dates and quality indicators without losing source evidence?
- Do transaction monetary fields require additional validation, and what verified rules are needed before defining revenue measures from preserved transaction source records?
- Do activity user/date repeats exist, how common are they, and do they represent additive contributions, repeated copies, or overlapping summaries?
- What are the precise count-category and `num_unq` semantics, and which daily aggregation rules are justified if multiple records contribute to one user/date?
- What definition should distinguish an observed activity day from an active listening day, and can a defensible `total_plays` measure be derived from the supplied count categories?
- What is the most efficient bounded-memory or database-assisted method for generating and maintaining the canonical customer universe across all relevant sources?
- What daily aggregate cardinality, partition size, temporary disk budget, and Power BI detail requirements should guide the physical activity design?

These questions are not resolved by this document. SQL and ETL implementation should follow the corresponding validation and design decisions.
