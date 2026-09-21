# Core Analytics Findings

## Dataset Scope

This analysis uses the finished V1 analytics layer: canonical users from the
currently staged member, churn-label, and transaction sources; two expiry-cohort
churn files; and both preserved transaction files. User logs are not loaded or
analyzed in V1.

| Analytical population | Records / users |
| --- | ---: |
| Canonical users | 7,207,283 |
| February 2017 churn observations | 992,931 |
| March 2017 churn observations | 970,960 |
| Preserved transaction records | 22,978,755 |
| Distinct transacting users | 2,426,143 |

Transaction rows are source records, not proven unique economic payments. The
two files are preserved without customer/date deduplication, and their monetary
fields are not treated as revenue.

## Subscriber and Metadata Coverage

| Member-enrichment status | Users | % canonical users |
| --- | ---: | ---: |
| With member metadata | 6,769,473 | 93.9255% |
| Without member metadata | 437,810 | 6.0745% |
| **Canonical users** | **7,207,283** | **100.0000%** |

The 437,810 users without member rows remain in the canonical universe. Their
optional demographic and registration fields are NULL rather than excluding
their churn or transaction records.

## Churn and Retention

The rates below use all users in each expiry cohort as the denominator.

| Expiry cohort | Users | Churned | Non-churned | Churn rate | Non-churn / retention rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2017-02-01 | 992,931 | 63,471 | 929,460 | 6.3923% | 93.6077% |
| 2017-03-01 | 970,960 | 87,330 | 883,630 | 8.9942% | 91.0058% |

March's observed churn rate is 2.6019 percentage points above February's. These
are separate expiry-cohort outcomes evaluated over the following 30 days, not a
timeless customer status.

### Member characteristics

All characteristic rates use the displayed cohort-group sample as denominator.
They are descriptive associations, not explanations of churn.

| Cohort | Gender / availability group | Users | Churned | Churn rate |
| --- | --- | ---: | ---: | ---: |
| Feb | Missing gender | 485,469 | 23,397 | 4.8195% |
| Feb | Male | 206,284 | 18,245 | 8.8446% |
| Feb | Female | 185,408 | 16,013 | 8.6366% |
| Feb | No member metadata | 115,770 | 5,816 | 5.0238% |
| Mar | Missing gender | 472,062 | 31,112 | 6.5907% |
| Mar | Male | 204,561 | 26,396 | 12.9037% |
| Mar | Female | 184,344 | 23,940 | 12.9866% |
| Mar | No member metadata | 109,993 | 5,882 | 5.3476% |

Male and female rates are close within each cohort. Missing gender is common,
so populated-gender groups do not represent the whole cohort.

| Cohort | Age-quality group | Users | Churned | Churn rate |
| --- | --- | ---: | ---: | ---: |
| Feb | Valid age | 389,140 | 34,414 | 8.8436% |
| Feb | Zero / unknown | 487,488 | 23,180 | 4.7550% |
| Feb | No member metadata | 115,770 | 5,816 | 5.0238% |
| Feb | Above 100 | 458 | 59 | 12.8821% |
| Feb | Negative | 75 | 2 | 2.6667% |
| Mar | Valid age | 386,715 | 51,324 | 13.2718% |
| Mar | Zero / unknown | 473,729 | 30,050 | 6.3433% |
| Mar | No member metadata | 109,993 | 5,882 | 5.3476% |
| Mar | Above 100 | 454 | 69 | 15.1982% |
| Mar | Negative | 69 | 5 | 7.2464% |

The negative and above-100 samples are too small for substantive conclusions.
Among ages accepted by the project's 1-100 convention:

| Valid age band | Feb users | Feb churn rate | Mar users | Mar churn rate |
| --- | ---: | ---: | ---: | ---: |
| 1-17 | 9,279 | 19.7758% | 9,796 | 27.9910% |
| 18-24 | 104,506 | 12.6931% | 104,948 | 18.3939% |
| 25-34 | 179,263 | 7.2625% | 177,130 | 11.0732% |
| 35-44 | 67,207 | 6.8430% | 66,310 | 10.5550% |
| 45-54 | 22,417 | 5.8839% | 22,122 | 9.3753% |
| 55-64 | 5,308 | 5.4069% | 5,257 | 8.7883% |
| 65-100 | 1,160 | 7.7586% | 1,152 | 11.1979% |

City and registration values are opaque source codes. The largest city-code
groups with at least about 20,000 users per cohort show the following results:

| City code | Feb users | Feb churn rate | Mar users | Mar churn rate |
| --- | ---: | ---: | ---: | ---: |
| 1 | 455,389 | 4.8411% | 442,598 | 6.4056% |
| 13 | 98,281 | 7.8733% | 97,136 | 12.3023% |
| 5 | 71,299 | 8.7631% | 70,706 | 13.1997% |
| 4 | 47,945 | 8.8935% | 47,227 | 12.9036% |
| 15 | 43,356 | 8.4233% | 43,187 | 12.8233% |
| 22 | 42,129 | 8.4241% | 41,991 | 12.5836% |
| 6 | 26,022 | 8.6043% | 26,066 | 12.8827% |
| 14 | 20,167 | 7.8445% | 20,013 | 11.8423% |

| Registration code / availability | Feb users | Feb churn rate | Mar users | Mar churn rate |
| --- | ---: | ---: | ---: | ---: |
| 7 | 482,726 | 3.0160% | 462,684 | 4.4732% |
| 9 | 236,620 | 8.6362% | 235,689 | 12.6832% |
| 3 | 105,445 | 12.7090% | 106,459 | 17.2254% |
| 4 | 49,283 | 18.2558% | 52,744 | 23.1022% |
| 13 | 3,087 | 8.5196% | 3,391 | 9.8791% |
| No member metadata | 115,770 | 5.0238% | 109,993 | 5.3476% |

These code-level differences are useful segmentation signals for a dashboard,
but the codes must not be given invented city or channel names.

## Churn Transitions

Exactly 881,701 users appear in both cohorts. Percentages use those shared users
as denominator.

| February label | March label | Users | % shared users |
| --- | --- | ---: | ---: |
| Non-churn | Non-churn | 824,659 | 93.5305% |
| Non-churn | Churn | 40,721 | 4.6185% |
| Churn | Non-churn | 5,269 | 0.5976% |
| Churn | Churn | 11,052 | 1.2535% |

In total, 45,990 shared users (5.2161%) changed label. This confirms churn is a
cohort-specific observation rather than a permanent user attribute.

## Transaction Behavior

| Scope | Records | Distinct users | Auto-renew records | Auto-renew share | Cancellation records | Cancellation share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `transactions.csv` | 21,547,746 | 2,363,626 | 18,357,950 | 85.1966% | 856,851 | 3.9765% |
| `transactions_v2.csv` | 1,431,009 | 1,197,050 | 1,123,775 | 78.5303% | 35,133 | 2.4551% |
| **All preserved records** | **22,978,755** | **2,426,143** | **19,481,725** | **84.7815%** | **891,984** | **3.8818%** |

`is_cancel` is a source cancellation flag and is not a churn label.

The reusable SQL returns all 27 months. Selected points illustrate the observed
record trend:

| Month | Transaction records | Unique transacting users | Auto-renew share | Cancellation share |
| --- | ---: | ---: | ---: | ---: |
| 2015-01 | 577,518 | 549,166 | 87.8314% | 4.1872% |
| 2015-12 | 944,133 | 862,805 | 83.6409% | 8.0088% |
| 2016-01 | 894,189 | 858,976 | 86.1963% | 6.2763% |
| 2016-12 | 1,018,086 | 989,458 | 87.4734% | 2.6634% |
| 2017-01 | 1,048,421 | 1,016,851 | 87.7958% | 2.8847% |
| 2017-02 | 1,037,179 | 1,000,365 | 88.1328% | 2.9871% |
| 2017-03 | 1,069,822 | 1,029,981 | 88.6063% | 2.9597% |

Because the v2 file contains historical-dated records, month-to-month changes
describe the combined preserved source records and are not asserted to be
unique payments.

| Payment-plan-day group | Records | % of 22,978,755 records |
| --- | ---: | ---: |
| 30 | 20,174,288 | 87.7954% |
| 0 | 872,342 | 3.7963% |
| 31 | 766,612 | 3.3362% |
| 1-29 | 641,357 | 2.7911% |
| 32-365 | 331,371 | 1.4421% |
| Over 365 | 192,785 | 0.8390% |

| Price relationship | Records | % of 22,978,755 records |
| --- | ---: | ---: |
| Paid equals list | 21,252,049 | 92.4856% |
| Paid below list | 867,020 | 3.7731% |
| Paid above list | 859,686 | 3.7412% |

| Expiry vs plan relationship | Records | % of 22,978,755 records |
| --- | ---: | ---: |
| Expiry longer | 12,231,703 | 53.2305% |
| Equal | 7,122,290 | 30.9951% |
| Expiry shorter | 3,624,762 | 15.7744% |

## Churn vs Transaction Behavior

For each churn observation, the comparison uses the three calendar months ending
with its expiry cohort: December-February for the February cohort and
January-March for the March cohort. Both transaction sources are retained; no
economic deduplication is inferred.

| Cohort | Churn label | Cohort users | Users with transaction records | User coverage | Records | Avg records per transacting user | Auto-renew record share | Cancellation-record share |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Feb | Non-churn | 929,460 | 927,455 | 99.7843% | 2,731,650 | 2.9453 | 93.2601% | 1.3229% |
| Feb | Churn | 63,471 | 54,200 | 85.3933% | 128,604 | 2.3728 | 60.1770% | 18.7288% |
| Mar | Non-churn | 883,630 | 882,959 | 99.9241% | 2,638,319 | 2.9880 | 93.5611% | 1.2819% |
| Mar | Churn | 87,330 | 76,749 | 87.8839% | 186,419 | 2.4289 | 63.0263% | 14.4197% |

These are descriptive differences in observed transaction records. They do not
show that auto-renew or cancellation causes a churn outcome. Cancellation and
churn retain different definitions.

## Data Quality / Interpretation Notes

| Observed source characteristic | Records | % of 22,978,755 records |
| --- | ---: | ---: |
| Negative expiry delta | 158,766 | 0.6909% |
| Zero expiry delta | 489,441 | 2.1300% |
| Expiry delta greater than 730 days | 52,465 | 0.2283% |
| Paid below list | 867,020 | 3.7731% |
| Paid above list | 859,686 | 3.7412% |
| Zero actual payment | 1,218,324 | 5.3020% |

- These conditions are retained observations, not automatic errors. The
  greater-than-730-day flag is a project convention.
- Long expiry deltas are concentrated in v2: 50,121 of 1,431,009 records
  (3.5025%), versus 2,344 of 21,547,746 original records (0.0109%).
- Source price values have no verified currency or net-revenue interpretation.
- Member gender is frequently missing, ages use a project cleaning convention,
  and city/registration codes have no verified descriptive mapping.
- Churn labels describe renewal outcomes after cohort expirations; neither the
  cohort anchor nor `is_cancel` is an exact churn event date.

## Key Findings

1. Member enrichment covers 6,769,473 of 7,207,283 canonical users (93.9255%);
   the remaining 437,810 users are retained rather than excluded.
2. Observed churn rose from 6.3923% in the February cohort to 8.9942% in March,
   a 2.6019 percentage-point difference.
3. Among 881,701 shared users, 824,659 (93.5305%) remained non-churn, while
   40,721 (4.6185%) moved from non-churn to churn.
4. The transaction layer contains 22,978,755 preserved records for 2,426,143
   users; 84.7815% are auto-renew records and 3.8818% are cancellation records.
5. Thirty-day plans account for 20,174,288 records (87.7954%), and paid equals
   list in 21,252,049 records (92.4856%).
6. In both three-month cohort windows, non-churned users have transaction-record
   coverage above 99.7%, versus 85.3933% and 87.8839% for churned users.
7. Auto-renew record share is about 93% for non-churned groups versus 60.1770%
   and 63.0263% for churned groups; cancellation-record share is 1.3229% and
   1.2819% versus 18.7288% and 14.4197%, respectively. These are associations,
   not causal estimates.
8. Most flagged source characteristics are uncommon overall, but the long-expiry
   flag differs sharply by source and should remain visible in quality reporting.

## Recommended Power BI KPIs

1. Canonical users.
2. Member metadata coverage rate.
3. Expiry-cohort users.
4. Cohort churn rate, with non-churn/retention rate alongside it.
5. Shared-user non-churn-to-churn transition rate.
6. Monthly transaction-record count.
7. Monthly unique transacting users.
8. Auto-renew and cancellation record shares, displayed separately and never
   relabeled as churn.
