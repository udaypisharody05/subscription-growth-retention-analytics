# KKBox Member Attribute Analysis

## Methodology

- Completed a sequential scan of 6,769,473 data rows, excluding the header.
- The exact six-column schema and record field counts were validated. Only attribute frequency distributions were retained; no customer identifiers are reported.
- Empty means an exactly empty CSV field. No trimming, normalization, replacement, deletion, capping, or other cleaning was performed.
- Distinct non-empty values use original field strings. Integer validation accepts an optional single sign followed by ASCII digits. Numeric summaries combine equivalent integer representations for statistical calculation only.
- bd quantiles exclude empty/non-integer values and use exact linear interpolation at zero-based position (N - 1) * p, weighted by frequencies. The median averages the two central values when N is even.
- Registration dates must have eight ASCII digits and be valid calendar dates. Each distinct value is parsed once, with row counts weighted by frequency.
- Percentages use all scanned rows as their denominator. Numeric/date ranges use only successfully parsed values. N/A indicates no applicable range.
- Thresholds for bd and registration dates are inspection checks, not decisions that the values are invalid.

## Completeness Summary

| Attribute | Empty rows | Empty % | Distinct non-empty values |
| --- | ---: | ---: | ---: |
| city | 0 | 0.0000% | 21 |
| bd | 0 | 0.0000% | 386 |
| gender | 4,429,505 | 65.4335% | 2 |
| registered_via | 0 | 0.0000% | 18 |
| registration_init_time | 0 | 0.0000% | 4,782 |

## City

- Total rows: 6,769,473.
- Empty values: 0.
- Distinct non-empty values: 21.
- Non-integer non-empty rows: 0.
- Minimum numeric value: 1.
- Maximum numeric value: 22.

| Source value | Rows | % of all rows |
| --- | ---: | ---: |
| (empty field) | 0 | 0.0000% |
| <code>1</code> | 4,804,326 | 70.9705% |
| <code>5</code> | 385,069 | 5.6883% |
| <code>13</code> | 320,978 | 4.7416% |
| <code>4</code> | 246,848 | 3.6465% |
| <code>22</code> | 210,407 | 3.1082% |
| <code>15</code> | 190,213 | 2.8099% |
| <code>6</code> | 135,200 | 1.9972% |
| <code>14</code> | 89,940 | 1.3286% |
| <code>12</code> | 66,843 | 0.9874% |
| <code>9</code> | 47,639 | 0.7037% |
| <code>11</code> | 47,489 | 0.7015% |
| <code>8</code> | 45,975 | 0.6792% |
| <code>18</code> | 38,039 | 0.5619% |
| <code>10</code> | 32,482 | 0.4798% |
| <code>21</code> | 30,837 | 0.4555% |
| <code>17</code> | 27,772 | 0.4103% |
| <code>3</code> | 27,282 | 0.4030% |
| <code>7</code> | 11,610 | 0.1715% |
| <code>16</code> | 5,092 | 0.0752% |
| <code>20</code> | 4,233 | 0.0625% |
| <code>19</code> | 1,199 | 0.0177% |

No real-world meanings are assigned to these source codes.

## bd

- Total rows: 6,769,473.
- Empty values: 0.
- Distinct non-empty values: 386.
- Non-integer non-empty rows: 0.
- Minimum numeric value: -7168.
- Maximum numeric value: 2016.
- Numeric rows: 6,769,473.
- Distinct numeric values: 386.

| Numeric check | Rows |
| --- | ---: |
| bd < 0 | 274 |
| bd = 0 | 4,540,215 |
| bd > 0 | 2,228,984 |
| bd > 100 | 5,377 |
| bd > 120 | 369 |

The positive thresholds overlap; they are not disjoint categories.

| Quantile | Numeric value |
| --- | ---: |
| p01 | 0 |
| p05 | 0 |
| p25 | 0 |
| median | 0 |
| p75 | 21 |
| p95 | 40 |
| p99 | 54 |

| Source value | Rows | % of all rows |
| --- | ---: | ---: |
| (empty field) | 0 | 0.0000% |
| <code>0</code> | 4,540,215 | 67.0690% |
| <code>22</code> | 112,200 | 1.6574% |
| <code>21</code> | 110,574 | 1.6334% |
| <code>20</code> | 110,452 | 1.6316% |
| <code>27</code> | 102,769 | 1.5181% |
| <code>23</code> | 101,500 | 1.4994% |
| <code>24</code> | 97,252 | 1.4366% |
| <code>26</code> | 92,433 | 1.3654% |
| <code>25</code> | 91,514 | 1.3519% |
| <code>19</code> | 91,374 | 1.3498% |
| <code>18</code> | 90,659 | 1.3392% |
| <code>28</code> | 82,722 | 1.2220% |
| <code>17</code> | 82,111 | 1.2130% |
| <code>29</code> | 82,026 | 1.2117% |
| <code>30</code> | 70,443 | 1.0406% |
| <code>32</code> | 64,607 | 0.9544% |
| <code>31</code> | 62,612 | 0.9249% |
| <code>33</code> | 58,559 | 0.8650% |
| <code>34</code> | 55,667 | 0.8223% |
| <code>37</code> | 54,381 | 0.8033% |

Top 20 of 386 distinct non-empty values shown. Frequencies for all values were calculated.

## Gender

- Total rows: 6,769,473.
- Empty values: 4,429,505.
- Distinct non-empty values: 2.

| Source value | Rows | % of all rows |
| --- | ---: | ---: |
| (empty field) | 4,429,505 | 65.4335% |
| <code>male</code> | 1,195,355 | 17.6580% |
| <code>female</code> | 1,144,613 | 16.9085% |

## registered_via

- Total rows: 6,769,473.
- Empty values: 0.
- Distinct non-empty values: 18.
- Non-integer non-empty rows: 0.
- Minimum numeric value: -1.
- Maximum numeric value: 19.

| Source value | Rows | % of all rows |
| --- | ---: | ---: |
| (empty field) | 0 | 0.0000% |
| <code>4</code> | 2,793,213 | 41.2619% |
| <code>3</code> | 1,643,208 | 24.2738% |
| <code>9</code> | 1,482,863 | 21.9051% |
| <code>7</code> | 805,895 | 11.9048% |
| <code>11</code> | 25,047 | 0.3700% |
| <code>13</code> | 5,455 | 0.0806% |
| <code>8</code> | 3,982 | 0.0588% |
| <code>5</code> | 3,115 | 0.0460% |
| <code>17</code> | 1,494 | 0.0221% |
| <code>2</code> | 1,452 | 0.0214% |
| <code>6</code> | 1,213 | 0.0179% |
| <code>19</code> | 974 | 0.0144% |
| <code>16</code> | 888 | 0.0131% |
| <code>14</code> | 615 | 0.0091% |
| <code>1</code> | 43 | 0.0006% |
| <code>10</code> | 10 | 0.0001% |
| <code>18</code> | 5 | 0.0001% |
| <code>-1</code> | 1 | 0.0000% |

No real-world meanings are assigned to these source codes.

## Registration Date

| Metric | Value |
| --- | ---: |
| Empty values | 0 |
| Invalid non-empty values | 0 |
| Minimum valid date | 2004-03-26 |
| Maximum valid date | 2017-04-29 |
| Valid-date rows before 2004-01-01 | 0 |
| Valid-date rows after 2017-12-31 | 0 |
| Distinct valid registration years | 14 |

| Registration year | Rows |
| --- | ---: |
| 2004 | 26,234 |
| 2005 | 41,349 |
| 2006 | 53,953 |
| 2007 | 89,830 |
| 2008 | 67,690 |
| 2009 | 63,633 |
| 2010 | 115,075 |
| 2011 | 179,051 |
| 2012 | 283,190 |
| 2013 | 524,722 |
| 2014 | 975,776 |
| 2015 | 1,620,525 |
| 2016 | 2,246,761 |
| 2017 | 481,684 |

## Data Quality Findings

- city: 0 empty rows.
- bd: 0 empty rows.
- gender: 4,429,505 empty rows.
- registered_via: 0 empty rows.
- registration_init_time: 0 empty rows.
- bd has 274 negative, 4,540,215 zero, 5,377 above-100, and 369 above-120 numeric rows. These counts do not establish a cleaning rule.
- Registration dates have 0 invalid non-empty rows, 0 valid rows before 2004-01-01, and 0 valid rows after 2017-12-31.

## Implications for dim_user

- city: all non-empty values are integer-like source codes. Code meanings and final representation are not assigned here.
- registered_via: all non-empty values are integer-like source codes. Code meanings and final representation are not assigned here.
- Fields with reported empty values need an explicit missing-value policy. Gender values remain as observed; no normalization or remapping is prescribed.
- bd has 0 non-integer rows and the numeric threshold counts above. Validate its meaning and quality before treating it as an analytical age. Zero, negative values, and high values were not altered.
- Registration-date typing must account for the reported empty and invalid values. The inspection boundaries do not define acceptable business dates.
- Final cleaning rules and SQL implementation are deferred; raw source values remain unchanged.
