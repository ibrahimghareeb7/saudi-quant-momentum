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

## Next Phases

Only after the clean data file is stable:

- SMA200
- Relative Strength 3M / 6M
- Liquidity Filter
- Risk-On / Risk-Off
