# KKBox Dataset Initial Inspection

> This report uses at most 10,000 rows from each CSV for schema and dtype inspection. It does not perform any full-file scans.

## Summary

| Filename | Size (bytes) | Size (GB) | Columns | Has `msno` |
| --- | ---: | ---: | ---: | :---: |
| members_v3.csv | 427921437 | 0.428 | 6 | Yes |
| train.csv | 46667771 | 0.047 | 2 | Yes |
| train_v2.csv | 45635134 | 0.046 | 2 | Yes |
| transactions.csv | 1729298376 | 1.729 | 9 | Yes |
| transactions_v2.csv | 115394513 | 0.115 | 9 | Yes |
| user_logs.csv | 30514081415 | 30.514 | 9 | Yes |
| user_logs_v2.csv | 1431465728 | 1.431 | 9 | Yes |

## members_v3.csv

- File size: 427921437 bytes (0.428 GB)
- Number of columns: 6
- Contains `msno`: Yes

### Columns

`msno`, `city`, `bd`, `gender`, `registered_via`, `registration_init_time`

### Sample-inferred dtypes

| Column | Pandas dtype |
| --- | --- |
| msno | str |
| city | int64 |
| bd | int64 |
| gender | str |
| registered_via | int64 |
| registration_init_time | int64 |

## train.csv

- File size: 46667771 bytes (0.047 GB)
- Number of columns: 2
- Contains `msno`: Yes

### Columns

`msno`, `is_churn`

### Sample-inferred dtypes

| Column | Pandas dtype |
| --- | --- |
| msno | str |
| is_churn | int64 |

## train_v2.csv

- File size: 45635134 bytes (0.046 GB)
- Number of columns: 2
- Contains `msno`: Yes

### Columns

`msno`, `is_churn`

### Sample-inferred dtypes

| Column | Pandas dtype |
| --- | --- |
| msno | str |
| is_churn | int64 |

## transactions.csv

- File size: 1729298376 bytes (1.729 GB)
- Number of columns: 9
- Contains `msno`: Yes

### Columns

`msno`, `payment_method_id`, `payment_plan_days`, `plan_list_price`, `actual_amount_paid`, `is_auto_renew`, `transaction_date`, `membership_expire_date`, `is_cancel`

### Sample-inferred dtypes

| Column | Pandas dtype |
| --- | --- |
| msno | str |
| payment_method_id | int64 |
| payment_plan_days | int64 |
| plan_list_price | int64 |
| actual_amount_paid | int64 |
| is_auto_renew | int64 |
| transaction_date | int64 |
| membership_expire_date | int64 |
| is_cancel | int64 |

## transactions_v2.csv

- File size: 115394513 bytes (0.115 GB)
- Number of columns: 9
- Contains `msno`: Yes

### Columns

`msno`, `payment_method_id`, `payment_plan_days`, `plan_list_price`, `actual_amount_paid`, `is_auto_renew`, `transaction_date`, `membership_expire_date`, `is_cancel`

### Sample-inferred dtypes

| Column | Pandas dtype |
| --- | --- |
| msno | str |
| payment_method_id | int64 |
| payment_plan_days | int64 |
| plan_list_price | int64 |
| actual_amount_paid | int64 |
| is_auto_renew | int64 |
| transaction_date | int64 |
| membership_expire_date | int64 |
| is_cancel | int64 |

## user_logs.csv

- File size: 30514081415 bytes (30.514 GB)
- Number of columns: 9
- Contains `msno`: Yes

### Columns

`msno`, `date`, `num_25`, `num_50`, `num_75`, `num_985`, `num_100`, `num_unq`, `total_secs`

### Sample-inferred dtypes

| Column | Pandas dtype |
| --- | --- |
| msno | str |
| date | int64 |
| num_25 | int64 |
| num_50 | int64 |
| num_75 | int64 |
| num_985 | int64 |
| num_100 | int64 |
| num_unq | int64 |
| total_secs | float64 |

## user_logs_v2.csv

- File size: 1431465728 bytes (1.431 GB)
- Number of columns: 9
- Contains `msno`: Yes

### Columns

`msno`, `date`, `num_25`, `num_50`, `num_75`, `num_985`, `num_100`, `num_unq`, `total_secs`

### Sample-inferred dtypes

| Column | Pandas dtype |
| --- | --- |
| msno | str |
| date | int64 |
| num_25 | int64 |
| num_50 | int64 |
| num_75 | int64 |
| num_985 | int64 |
| num_100 | int64 |
| num_unq | int64 |
| total_secs | float64 |
