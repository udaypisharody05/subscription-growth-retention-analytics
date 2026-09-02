# Churn Label Analysis

## Methodology

- Both CSVs were scanned sequentially to completion. Only per-user label state and counters were retained; no customer identifiers or raw rows are reported.
- Only the exact strings 0 and 1 are valid labels. Empty labels are counted separately; other non-empty values are invalid. No normalization was applied.
- File churn/non-churn counts are row counts, including repeated customers. Churn rate is churn rows divided by all valid-label rows; missing and invalid labels are excluded from this denominator.
- Duplicate occurrences count rows beyond each user's first occurrence. A conflicting user has differing label strings within one file, including disagreements involving missing or invalid labels.
- Transitions count each shared user once. Users with conflicting labels or without a valid label in either file are excluded from transitions, not silently assigned a label. Identical repeated valid labels remain eligible.
- Transition and label-change percentages use all shared users as the denominator. When users are excluded, transition percentages need not sum to 100%.
- Observation months are not assigned; competition timing semantics require separate verification.

## File summary

| File | Total rows | Distinct users | Churn rows | Non-churn rows | Churn rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| train.csv | 992,931 | 992,931 | 63,471 | 929,460 | 6.39% |
| train_v2.csv | 970,960 | 970,960 | 87,330 | 883,630 | 8.99% |

## User overlap

| Metric | Users / percentage |
| --- | ---: |
| Users in both files | 881,701 |
| Users only in train.csv | 111,230 |
| Users only in train_v2.csv | 89,259 |
| Percentage of v2 users also in train.csv | 90.81% |

## Label transition matrix

| train.csv label | train_v2.csv label | Users | % shared users |
| --- | --- | ---: | ---: |
| 0 | 0 | 824,659 | 93.53% |
| 0 | 1 | 40,721 | 4.62% |
| 1 | 0 | 5,269 | 0.60% |
| 1 | 1 | 11,052 | 1.25% |

## Label stability

| Metric | Users | % shared users |
| --- | ---: | ---: |
| Label stayed the same | 835,711 | 94.78% |
| Label changed | 45,990 | 5.22% |
| Excluded: conflicting, invalid, or missing label | 0 | 0.00% |

## Duplicate / data-quality checks

| File | Duplicate occurrences beyond first | Distinct duplicated users | Conflicting duplicated users | Invalid non-empty labels | Missing labels |
| --- | ---: | ---: | ---: | ---: | ---: |
| train.csv | 0 | 0 | 0 | 0 | 0 |
| train_v2.csv | 0 | 0 | 0 | 0 | 0 |

## Conclusion

45,990 shared users have different valid, non-conflicting labels between the two files.

Churn is observed at different time periods and should not be modeled as a permanent user dimension attribute.

0 shared users were excluded from label-transition comparisons because of conflicting, invalid, or missing labels. No observation months are inferred by this analysis.
