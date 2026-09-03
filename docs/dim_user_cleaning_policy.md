# dim_user Cleaning Policy

This document defines proposed member-attribute transformations for the future `analytics.dim_user` table. It uses the verified profiling results and introduces no SQL or data changes. The age validity range below is an explicit project analytical convention, not an official KKBox rule.

## 1. Principles

- Source values must remain recoverable from immutable raw files and source-preserving staging. Analytical cleaning must not overwrite the raw data.
- Every analytical transformation must be explicit and distinguish preserved source values from derived values.
- Unknown or missing values must not be silently converted into demographic or channel categories.
- Member metadata is optional enrichment of the canonical customer universe, not a condition for membership in that universe.
- A cleaning rule must never exclude a canonical customer. Questionable attributes affect the corresponding analytical fields, not whether the customer exists.
- `has_member_metadata` describes the existence of a member record, not whether every attribute in that record is populated or analytically usable.

## 2. Proposed dim_user Member Fields

| Analytical field | Source | Proposed treatment |
| --- | --- | --- |
| `user_key` | Canonical customer identity process | Stable surrogate key, assigned independently of member metadata availability |
| `msno` | Customer identifiers across relevant sources | Preserve the anonymized natural identifier unchanged; member coverage must not restrict inclusion |
| `has_member_metadata` | Existence of a matching members_v3 record | True when a member record exists; false otherwise |
| `city_code` | `city` | Nullable integer-like source code; preserve every observed code without assigning city names |
| `bd_raw` | `bd` | Preserve the original integer value, including zero, negative, and high values; NULL only when member metadata is absent under the verified source conditions |
| `age` | Derived from `bd` | Retain values from 1 through 100 inclusive; otherwise NULL |
| `age_quality` | Member availability and `bd` | Explicit quality category: valid, zero_or_unknown, negative, above_100, or no_member_metadata |
| `gender` | `gender` | Preserve male/female; empty source values or absent metadata become NULL |
| `registered_via_code` | `registered_via` | Nullable integer-like source code; preserve all observed codes, including -1 |
| `registration_init_date` | `registration_init_time` | Parse the source calendar date to a future PostgreSQL DATE; NULL when member metadata is absent |

These treatments apply to the verified source values. Unexpected values in a future source version require review rather than an invented mapping or silent extension of this policy.

## 3. city

Verified findings: zero empty values, 21 distinct integer-like source codes, and a numeric range of 1 through 22. No mapping to actual city names has been verified.

Policy:

- Preserve the source code as nullable `city_code`.
- Do not convert codes to city names.
- Do not treat code 1, or any other code, as an unknown-value marker without evidence.
- Set `city_code` to NULL for customers without member metadata.

## 4. bd / Age

The dataset documentation describes `bd` as age and warns of extreme outlier values. Profiling found no empty or non-integer values, but the numeric range is -7168 through 2016, with 386 distinct numeric values.

| Verified check | Result |
| --- | ---: |
| bd < 0 | 274 rows |
| bd = 0 | 4,540,215 rows (67.0690%) |
| bd > 0 | 2,228,984 rows |
| bd > 100 | 5,377 rows |
| bd > 120 | 369 rows |
| Median | 0 |
| p75 | 21 |
| p95 | 40 |
| p99 | 54 |

The above-100 and above-120 counts overlap the positive-value count; they are not separate disjoint categories.

Preserve `bd_raw` as the original integer whenever member metadata exists. Derive `age` and `age_quality` separately:

| Condition | `bd_raw` | `age` | `age_quality` |
| --- | --- | --- | --- |
| No member metadata | NULL | NULL | no_member_metadata |
| bd < 0 | Original integer | NULL | negative |
| bd = 0 | 0 | NULL | zero_or_unknown |
| 1 <= bd <= 100 | Original integer | bd | valid |
| bd > 100 | Original integer | NULL | above_100 |

Rationale:

- Zero dominates the field and is not analytically useful as literal age in this project's demographic analysis.
- Negative values cannot represent a conventional age.
- The source contains extreme values as high as 2016.
- Values above 100 are sufficiently unusual that they should not be used in standard demographic analysis without further evidence. This does not assert that every age above 100 is impossible.

The inclusive 1-100 range is a project-level analytical quality convention. It is NOT claimed to be an official KKBox validity threshold, and it does not correct or replace the raw source. The `valid` category means accepted by this convention, not independently verified as a customer's true age. The `zero_or_unknown` category is a quality classification, not a claim about the official meaning of source zero.

`bd_raw` remains available so the rule can be revised later. Do not cap values, delete customers, alter raw `bd`, or create age buckets at this stage.

## 5. gender

Verified findings:

- 4,429,505 member rows have empty gender (65.4335%).
- 1,195,355 rows contain male.
- 1,144,613 rows contain female.
- No other non-empty values were observed.

Preserve the observed `male` and `female` values. Convert an empty source gender to NULL in the analytical field. Customers without member metadata also receive NULL.

Do not store an artificial Unknown category in the dimension. A presentation layer may display such a label if explicitly needed, without changing the stored NULL. The original empty source value remains recoverable through the preserved source/staging data.

Approximately 65.43% of member rows lack gender. Gender-based analysis must disclose this substantial missingness as well as any additional lack of member metadata in the analytical population.

## 6. registered_via

Verified findings: zero empty values, 18 distinct integer-like source codes, and a range of -1 through 19. One row contains -1; code meanings have not been verified.

Preserve the numeric source value as `registered_via_code`. Do not map codes to registration-channel names without verified metadata. In particular, preserve -1 as a source code rather than automatically converting it to NULL.

Customers without member metadata receive NULL. Code opacity alone is not a reason to discard a source value or remove a customer.

## 7. registration_init_time

All 6,769,473 observed values are non-empty, valid calendar dates. The observed range is 2004-03-26 through 2017-04-29.

Parse the source YYYYMMDD value into a PostgreSQL DATE in the future staging/analytics layer and expose it as `registration_init_date`. Preserve the original source representation in the immutable CSV and, where useful for lineage, staging.

Do not impose additional arbitrary date filtering on these verified values. Customers without member metadata receive NULL.

## 8. Missing Member Metadata

Customers found in transactions, churn labels, or activity sources but absent from `members_v3` must still exist in `dim_user`, with their canonical `user_key` and `msno` preserved.

| Field | Value when member metadata is absent |
| --- | --- |
| `has_member_metadata` | false |
| `city_code` | NULL |
| `bd_raw` | NULL |
| `age` | NULL |
| `age_quality` | no_member_metadata |
| `gender` | NULL |
| `registered_via_code` | NULL |
| `registration_init_date` | NULL |

Do not drop these users or their otherwise valid facts. A member record with a missing gender or an unusable analytical age still has `has_member_metadata` set to true.

## 9. Analytical Caveats

- `age` is derived under a project convention and must not be confused with the untouched source `bd`, preserved as `bd_raw`.
- Gender has very high missingness; populated-gender results do not describe the entire customer population without qualification.
- City and registration-channel values remain opaque source codes. No descriptive mapping is inferred.
- Demographic analysis should disclose member coverage, missingness, and the number of observations excluded from a particular attribute-based analysis by its quality rule.
- Attribute-level exclusion from a demographic calculation must not become exclusion from the customer universe.
- No demographic or registration field should determine whether a user belongs in the canonical customer universe.

## 10. Final Policy Summary

| Source field | Preserved field / source evidence | Derived analytical field | Treatment of questionable values |
| --- | --- | --- | --- |
| `msno` | `msno` | `user_key` from canonical identity assignment | Preserve identity; absence of member metadata must not exclude the user |
| `city` | `city_code`; immutable source | No descriptive city mapping | Keep observed integer-like codes, including 1; NULL only when member metadata is absent under the verified source conditions |
| `bd` | `bd_raw`; immutable source | `age`, `age_quality` | Age 1-100 inclusive is retained by project convention; zero, negative, above-100, and absent metadata yield NULL age with the appropriate quality category |
| `gender` | Original value in immutable source/staging | Nullable `gender` | Preserve male/female; empty or absent metadata becomes NULL, not a stored Unknown category |
| `registered_via` | `registered_via_code`; immutable source | No descriptive channel mapping | Preserve all observed codes, including -1; NULL when member metadata is absent |
| `registration_init_time` | Original YYYYMMDD value in immutable source and optional staging lineage | `registration_init_date` | Parse verified valid dates without arbitrary filtering; NULL when member metadata is absent |

No SQL, age buckets, city mappings, or channel mappings are introduced by this policy.
