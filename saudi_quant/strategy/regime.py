from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


TASI_PROXY_COLUMNS = [
    "date",
    "equal_weight_return",
    "tasi_proxy_close",
    "tasi_proxy_sma200",
    "above_tasi_sma200",
    "regime_valid",
]
BREADTH_COLUMNS = ["date", "tickers_with_sma200", "tickers_above_sma200", "breadth"]
REGIME_COLUMNS = [
    "date",
    "tasi_proxy_close",
    "tasi_proxy_sma200",
    "above_tasi_sma200",
    "breadth",
    "regime_valid",
    "regime",
]
PRICE_REQUIRED_COLUMNS = ["date", "ticker", "close"]
SMA_REQUIRED_COLUMNS = ["date", "ticker", "above_sma200"]


@dataclass(frozen=True)
class RegimeV2Config:
    prices_path: Path = Path("prices_v2.csv")
    sma200_path: Path = Path("sma200_v2.csv")
    tasi_output_path: Path = Path("tasi_proxy_v2.csv")
    breadth_output_path: Path = Path("breadth_v2.csv")
    regime_output_path: Path = Path("regime_v2.csv")


def run_regime_v2(config: RegimeV2Config | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    config = config or RegimeV2Config()
    _ensure_v2_sources(config.prices_path, config.sma200_path)
    _ensure_outputs_do_not_exist(config.tasi_output_path, config.breadth_output_path, config.regime_output_path)

    prices = load_prices_v2(config.prices_path)
    sma200 = load_sma200_v2(config.sma200_path)
    tasi_proxy = build_tasi_proxy(prices)
    breadth = build_breadth(sma200)
    regime = build_regime(tasi_proxy, breadth)

    config.tasi_output_path.parent.mkdir(parents=True, exist_ok=True)
    config.breadth_output_path.parent.mkdir(parents=True, exist_ok=True)
    config.regime_output_path.parent.mkdir(parents=True, exist_ok=True)
    tasi_proxy.to_csv(config.tasi_output_path, index=False)
    breadth.to_csv(config.breadth_output_path, index=False)
    regime.to_csv(config.regime_output_path, index=False)
    return tasi_proxy, breadth, regime


def load_prices_v2(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Prices file not found: {path}")

    prices = pd.read_csv(path)
    missing = [column for column in PRICE_REQUIRED_COLUMNS if column not in prices.columns]
    if missing:
        raise ValueError(f"Prices file is missing required columns: {', '.join(missing)}")
    return prices


def load_sma200_v2(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"SMA200 file not found: {path}")

    sma200 = pd.read_csv(path)
    missing = [column for column in SMA_REQUIRED_COLUMNS if column not in sma200.columns]
    if missing:
        raise ValueError(f"SMA200 file is missing required columns: {', '.join(missing)}")
    return sma200


def build_tasi_proxy(prices: pd.DataFrame) -> pd.DataFrame:
    clean = prices[["date", "ticker", "close"]].copy()
    clean["date"] = pd.to_datetime(clean["date"], errors="coerce")
    clean["ticker"] = clean["ticker"].astype("string").str.upper()
    clean["close"] = pd.to_numeric(clean["close"], errors="coerce")
    clean = clean.dropna(subset=["date", "ticker", "close"])
    clean = clean.sort_values(["ticker", "date"], kind="stable").reset_index(drop=True)
    clean["daily_return"] = clean.groupby("ticker")["close"].pct_change()

    daily = clean.groupby("date", as_index=False)["daily_return"].mean()
    daily["equal_weight_return"] = daily["daily_return"].fillna(0.0)
    daily["tasi_proxy_close"] = 100.0 * (1.0 + daily["equal_weight_return"]).cumprod()
    daily["tasi_proxy_sma200"] = daily["tasi_proxy_close"].rolling(window=200, min_periods=200).mean()
    daily["regime_valid"] = daily["tasi_proxy_sma200"].notna()
    daily["above_tasi_sma200"] = daily["regime_valid"] & (daily["tasi_proxy_close"] > daily["tasi_proxy_sma200"])
    daily["date"] = daily["date"].dt.strftime("%Y-%m-%d")
    daily["equal_weight_return"] = daily["equal_weight_return"].round(6)
    daily["tasi_proxy_close"] = daily["tasi_proxy_close"].round(4)
    daily["tasi_proxy_sma200"] = daily["tasi_proxy_sma200"].round(4)
    return daily[TASI_PROXY_COLUMNS]


def build_breadth(sma200: pd.DataFrame) -> pd.DataFrame:
    clean = sma200[["date", "ticker", "above_sma200"]].copy()
    clean["date"] = pd.to_datetime(clean["date"], errors="coerce")
    clean["ticker"] = clean["ticker"].astype("string").str.upper()
    clean["above_sma200"] = pd.to_numeric(clean["above_sma200"], errors="coerce")
    clean = clean.dropna(subset=["date", "ticker", "above_sma200"])
    clean["above_sma200"] = clean["above_sma200"].astype(bool)

    breadth = clean.groupby("date").agg(
        tickers_with_sma200=("ticker", "nunique"),
        tickers_above_sma200=("above_sma200", "sum"),
    )
    breadth = breadth.reset_index()
    breadth["breadth"] = breadth["tickers_above_sma200"] / breadth["tickers_with_sma200"]
    breadth["date"] = breadth["date"].dt.strftime("%Y-%m-%d")
    breadth["breadth"] = breadth["breadth"].round(6)
    return breadth[BREADTH_COLUMNS]


def build_regime(tasi_proxy: pd.DataFrame, breadth: pd.DataFrame) -> pd.DataFrame:
    regime = tasi_proxy.merge(
        breadth[["date", "breadth"]],
        on="date",
        how="left",
        validate="one_to_one",
    )
    regime["breadth"] = regime["breadth"].fillna(0.0)
    is_risk_on = (regime["above_tasi_sma200"] == True) & (regime["breadth"] > 0.55)
    regime["regime"] = is_risk_on.map({True: "Risk-On", False: "Risk-Off"})
    regime.loc[~regime["regime_valid"], "regime"] = "REGIME_UNAVAILABLE"
    return regime[REGIME_COLUMNS]


def _ensure_v2_sources(prices_path: Path, sma200_path: Path) -> None:
    if prices_path.name != "prices_v2.csv":
        raise ValueError("Regime v2 must use prices_v2.csv only.")
    if sma200_path.name != "sma200_v2.csv":
        raise ValueError("Regime v2 must use sma200_v2.csv only.")


def _ensure_outputs_do_not_exist(*paths: Path) -> None:
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        joined = ", ".join(existing)
        raise FileExistsError(f"Refusing to overwrite existing output file(s): {joined}")
