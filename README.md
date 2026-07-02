# Saudi Quant Momentum

Data-first Saudi market momentum project.

The first version intentionally contains only the EOD data pipeline. No dashboard, no AI, no Telegram, and no strategy logic yet.

## Current Goal

Generate a clean `prices.csv` file with:

```text
date, ticker, open, high, low, close, volume, traded_value
```

## Test Universe

- `1120.SR` Al Rajhi Bank
- `2222.SR` Saudi Aramco
- `7010.SR` STC
- `1180.SR` Saudi National Bank
- `2010.SR` SABIC
- `1211.SR` Maaden
- `1150.SR` Alinma Bank
- `2380.SR` Petro Rabigh
- `7203.SR` Elm
- `2082.SR` ACWA Power

## Setup

```powershell
python -m pip install -r requirements.txt
```

## Run

```powershell
python main.py
```

By default, this writes:

```text
prices.csv
```

The default date window starts at `2010-01-01` and uses today's date as an exclusive end date, so the current trading day is not pulled before it is complete.

You can also choose an output path:

```powershell
python main.py --output output/prices.csv
```

To include adjusted close when Yahoo Finance provides it:

```powershell
python main.py --include-adjusted-close
```

## Data Quality Audit

Before any momentum, ranking, or backtest work, audit the raw prices file:

```powershell
python main.py data-quality
```

This does not modify `prices.csv`. It writes:

```text
data_quality_report.csv
suspicious_price_moves.csv
```

## Price Adjustment Audit

Before any strategy or backtest work, audit likely adjusted/unadjusted price issues:

```powershell
python main.py adjustment-audit
```

This does not modify `prices.csv` and does not overwrite existing audit outputs. It writes:

```text
adjustment_audit_report.csv
ticker_quality_summary.csv
```

## V2 Post-2014 Dataset

Build the v2 dataset and rerun the required quality gates from `2014-01-01` onward:

```powershell
python main.py v2-post-2014
```

This filters `prices.csv` without modifying it. It writes:

```text
prices_v2.csv
data_quality_report_v2.csv
suspicious_price_moves_v2.csv
adjustment_audit_report_v2.csv
ticker_quality_summary_v2.csv
sma200_v2.csv
```

## SMA200

After `prices.csv` exists, build the first indicator file:

```powershell
python main.py sma200
```

This writes:

```text
sma200.csv
```

with:

```text
date, ticker, close, sma200, above_sma200
```

## Next Phases

Only after the clean data file is stable:

- Relative Strength 3M / 6M
- Liquidity Filter
- Risk-On / Risk-Off
