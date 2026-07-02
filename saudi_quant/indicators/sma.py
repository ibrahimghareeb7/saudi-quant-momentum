from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


SMA200_COLUMNS = ["date", "ticker", "close", "sma200", "above_sma200"]


@dataclass(frozen=True)
class SMA200Config:
    prices_path: Path = Path("prices.csv")
    output_path: Path = Path("sma200.csv")
    window: int = 200


def run_sma200_pipeline(config: SMA200Config | None = None) -> pd.DataFrame:
    config = config or SMA200Config()
    prices = load_prices(config.prices_path)
    sma200 = calculate_sma200(prices, window=config.window)

    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    sma200.to_csv(config.output_path, index=False)
    return sma200


def load_prices(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Prices file not found: {path}")

    prices = pd.read_csv(path)
    missing = [column for column in ["date", "ticker", "close"] if column not in prices.columns]
    if missing:
        raise ValueError(f"Prices file is missing required columns: {', '.join(missing)}")

    return prices


def calculate_sma200(prices: pd.DataFrame, window: int = 200) -> pd.DataFrame:
    if window <= 0:
        raise ValueError("window must be greater than zero")

    clean = prices[["date", "ticker", "close"]].copy()
    clean["date"] = pd.to_datetime(clean["date"], errors="coerce")
    clean["ticker"] = clean["ticker"].astype("string").str.upper()
    clean["close"] = pd.to_numeric(clean["close"], errors="coerce")
    clean = clean.dropna(subset=["date", "ticker", "close"])
    clean = clean.sort_values(["ticker", "date"], kind="stable").reset_index(drop=True)

    clean["sma200"] = clean.groupby("ticker")["close"].transform(
        lambda close: close.rolling(window=window, min_periods=window).mean()
    )
    clean = clean.dropna(subset=["sma200"]).copy()

    clean["date"] = clean["date"].dt.strftime("%Y-%m-%d")
    clean["close"] = clean["close"].round(4)
    clean["sma200"] = clean["sma200"].round(4)
    clean["above_sma200"] = (clean["close"] > clean["sma200"]).astype("int8")

    clean = clean[SMA200_COLUMNS]
    clean = clean.sort_values(["date", "ticker"], kind="stable").reset_index(drop=True)
    return clean
