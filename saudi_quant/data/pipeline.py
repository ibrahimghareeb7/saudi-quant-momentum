from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
import yfinance as yf

from saudi_quant.config.universe import test_tickers


BASE_COLUMNS = [
    "date",
    "ticker",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "traded_value",
]


@dataclass(frozen=True)
class DataPipelineConfig:
    output_path: Path = Path("prices.csv")
    tickers: tuple[str, ...] = tuple(test_tickers())
    start: str | None = "2010-01-01"
    end: str | None = None
    period: str = "max"
    include_adjusted_close: bool = False


def run_pipeline(config: DataPipelineConfig | None = None) -> pd.DataFrame:
    config = config or DataPipelineConfig()
    prices = download_prices(config)
    clean = clean_prices(prices, include_adjusted_close=config.include_adjusted_close)

    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    clean.to_csv(config.output_path, index=False)
    return clean


def download_prices(config: DataPipelineConfig) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    failures: list[str] = []

    for ticker in config.tickers:
        date_kwargs = _download_date_kwargs(config)
        try:
            downloaded = yf.download(
                ticker,
                **date_kwargs,
                interval="1d",
                auto_adjust=False,
                actions=False,
                progress=False,
                threads=False,
            )
        except Exception as exc:  # pragma: no cover - network/provider failures vary.
            failures.append(f"{ticker}: {exc}")
            continue

        if downloaded.empty:
            failures.append(f"{ticker}: no rows returned")
            continue

        frame = _normalise_provider_frame(downloaded, ticker)
        frames.append(frame)

    if not frames:
        detail = "; ".join(failures) if failures else "no tickers configured"
        raise RuntimeError(f"No price data downloaded: {detail}")

    return pd.concat(frames, ignore_index=True)


def clean_prices(prices: pd.DataFrame, include_adjusted_close: bool = False) -> pd.DataFrame:
    clean = prices.copy()

    clean["date"] = pd.to_datetime(clean["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    clean["ticker"] = clean["ticker"].astype("string").str.upper()

    numeric_columns = ["open", "high", "low", "close", "volume", "adjusted_close"]
    for column in numeric_columns:
        if column in clean.columns:
            clean[column] = pd.to_numeric(clean[column], errors="coerce")

    required = ["date", "ticker", "open", "high", "low", "close", "volume"]
    clean = clean.dropna(subset=required)

    price_columns = ["open", "high", "low", "close", "adjusted_close"]
    for column in price_columns:
        if column in clean.columns:
            clean[column] = clean[column].round(4)

    clean["volume"] = clean["volume"].round().astype("int64")
    clean["traded_value"] = (clean["close"] * clean["volume"]).round(2)

    output_columns = BASE_COLUMNS.copy()
    if include_adjusted_close and "adjusted_close" in clean.columns:
        output_columns.insert(7, "adjusted_close")

    clean = clean[output_columns]
    clean = clean.sort_values(["date", "ticker"], kind="stable").reset_index(drop=True)
    return clean


def _download_date_kwargs(config: DataPipelineConfig) -> dict[str, str | None]:
    if config.start or config.end:
        return {
            "start": config.start,
            "end": config.end or date.today().isoformat(),
        }

    return {"period": config.period}


def _normalise_provider_frame(downloaded: pd.DataFrame, ticker: str) -> pd.DataFrame:
    frame = _flatten_columns(downloaded, ticker).reset_index()
    frame = frame.rename(columns={column: _normalise_column_name(column) for column in frame.columns})

    if "index" in frame.columns and "date" not in frame.columns:
        frame = frame.rename(columns={"index": "date"})

    keep_columns = ["date", "open", "high", "low", "close", "adj_close", "volume"]
    present_columns = [column for column in keep_columns if column in frame.columns]
    frame = frame[present_columns].copy()

    if "adj_close" in frame.columns:
        frame = frame.rename(columns={"adj_close": "adjusted_close"})

    frame["ticker"] = ticker
    return frame


def _flatten_columns(downloaded: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if not isinstance(downloaded.columns, pd.MultiIndex):
        return downloaded.copy()

    columns = downloaded.columns
    if ticker in columns.get_level_values(0):
        return downloaded.xs(ticker, axis=1, level=0).copy()

    if ticker in columns.get_level_values(-1):
        return downloaded.xs(ticker, axis=1, level=-1).copy()

    flat = downloaded.copy()
    flat.columns = ["_".join(str(part) for part in column if part) for column in columns]
    return flat


def _normalise_column_name(column: object) -> str:
    name = str(column).strip().lower()
    return name.replace(" ", "_")
