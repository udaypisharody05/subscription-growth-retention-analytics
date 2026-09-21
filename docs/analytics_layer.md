# Core Analytics Layer

## Scope

Migration 003 implements the smallest V1 analytics layer needed for SQL analysis
and Power BI over the completed member, churn-label, and transaction staging
loads. It does not load user logs, create activity facts, or define revenue,
MRR, ARPU, or LTV.

## Grains and Canonical User Universe

`analytics.dim_user` has one row per distinct canonical `msno`. The V1 universe
is the union of identities in `staging.members`, `staging.churn_labels`, and
`staging.transactions`. This prevents `members_v3.csv` from becoming an
inclusion filter. User-log identities are deferred until bounded activity
aggregation is implemented.

Member attributes are optional enrichment applied with left-join semantics.
`has_member_metadata` distinguishes enriched users from users whose city,
gender, registration channel/date, and raw age fields are NULL because no
member record exists.

| Dimension result | Rows |
| --- | ---: |
| Canonical users | 7,207,283 |
| Users with member metadata | 6,769,473 |
| Users without member metadata | 437,810 |

`user_key` is a stable surrogate key, while `msno` remains unique. Churn is not
stored on this dimension.

## Age Convention

`bd_raw` preserves the member source value. `analytical_age` retains values from
1 through 100 inclusive and is NULL otherwise. `age_quality` records one of:

- `valid`
- `zero_or_unknown`
- `negative`
- `above_100`
- `no_member_metadata`

The 1-100 range is a project analytical convention, not an official KKBox
validity rule.

## Churn Observations

`analytics.fact_churn_observation` has one row per canonical user and expiry
cohort month. It retains `source_file_key`, the 1-based `source_row_number`, and
the readable label source. It contains `is_churn` and the cohort anchor but no
invented churn event date.

| Expiry cohort | Observations | Churn TRUE | Churn FALSE |
| --- | ---: | ---: | ---: |
| 2017-02-01 | 992,931 | 63,471 | 929,460 |
| 2017-03-01 | 970,960 | 87,330 | 883,630 |
| **Total** | **1,963,891** | **150,801** | **1,813,090** |

The cohort month is a first-day anchor. Outcomes are evaluated over the
following 30 days, and `is_cancel` remains distinct from churn.

## Transaction Layer

`analytics.fact_transaction` is a view over `staging.transactions`, joined to
the canonical user and registered source file. This avoids a redundant physical
copy of 22,978,755 rows while exposing both source versions, their exact lineage,
all typed transaction fields, and the existing deterministic price and expiry
validation fields.

The view contains 21,547,746 records from `transactions.csv` and 1,431,009 from
`transactions_v2.csv`. It performs no customer/date deduplication and preserves
unusual values. Monetary source fields remain uninterpreted; the layer creates
no revenue or subscription-value KPI.

## Reusable Views

| View | Grain / purpose |
| --- | --- |
| `analytics.v_monthly_transaction_activity` | Transaction month and source; transaction/user counts plus cancellation and expiry flags |
| `analytics.v_churn_cohort_summary` | Expiry cohort; observation, churn, non-churn, and churn-rate summary |
| `analytics.v_member_metadata_coverage` | One-row canonical-user member coverage summary |
| `analytics.v_transaction_relationship_anomaly_summary` | Transaction source; price, plan/expiry, cancellation, and expiry-anomaly counts |

## Verification

The automated read-only verification proved that the dimension exactly equals
the distinct identity union of the three staged source groups, has no duplicate
keys or identifiers, and applies member enrichment and age rules correctly. It
also proved exact churn observation/lineage preservation, exact cohort and
TRUE/FALSE counts, and complete transaction-view coverage for both sources.

Verified source state remained unchanged: `raw.source_file` has 7 rows,
`staging.members` has 6,769,473 rows, `staging.churn_labels` has 1,963,891 rows,
and `staging.transactions` has 22,978,755 rows. No user-log or activity fact was
created, and no unsupported revenue metric exists in the analytics schema.
