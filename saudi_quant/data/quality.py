from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


PRICE_COLUMNS = ["open", "high", "low", "close"]
REQUIRED_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "volume", "traded_value"]
REPORT_COLUMNS = [
    "section",
    "check",
    "ticker",
    "column",
    "issue_count",
    "trading_day_count",
    "first_date",
    "last_date",
    "min_value",
    "max_value",
    "notes",
]
SUSPICIOUS_MOVE_COLUMNS = [
    "date",
    "ticker",
    "previous_close",
    "close",
    "daily_return",
]


@dataclass(frozen=True)
class DataQualityConfig:
    prices_path: Path = Path("prices.csv")
    report_output_path: Path = Path("data_quality_report.csv")
    moves_output_path: Path = Path("suspicious_price_moves.csv")
    return_threshold: float = 0.15


def run_data_quality_audit(config: DataQualityConfig | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    config = config or DataQualityConfig()
    prices = load_prices_for_audit(config.prices_path)
    report, suspicious_moves = audit_prices(prices, return_threshold=config.return_threshold)

    config.report_output_path.parent.mkdir(parents=True, exist_ok=True)
    config.moves_output_path.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(config.report_output_path, index=False)
    suspicious_moves.to_csv(config.moves_output_path, index=False)
    return report, suspicious_moves


def load_prices_for_audit(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Prices file not found: {path}")

    prices = pd.read_csv(path)
    missing = [column for column in REQUIRED_COLUMNS if column not in prices.columns]
    if missing:
        raise ValueError(f"Prices file is missing required columns: {', '.join(missing)}")

    return prices


def audit_prices(prices: pd.DataFrame, return_threshold: float = 0.15) -> tuple[pd.DataFrame, pd.DataFrame]:
    if return_threshold <= 0:
        raise ValueError("return_threshold must be greater than zero")

    clean = _normalise_prices(prices)
    rows: list[dict[str, object]] = []

    _append_dataset_summary(rows, clean)
    _append_ticker_coverage(rows, clean)
    _append_missing_value_checks(rows, clean)
    _append_price_value_checks(rows, clean)
    _append_range_checks(rows, clean)
    _append_duplicate_checks(rows, clean)

    suspicious_moves = _find_suspicious_moves(clean, return_threshold=return_threshold)
    _append_suspicious_move_summary(rows, suspicious_moves, return_threshold=return_threshold)

    report = pd.DataFrame(rows, columns=REPORT_COLUMNS)
    report = report.fillna("")
    suspicious_moves = suspicious_moves[SUSPICIOUS_MOVE_COLUMNS]
    return report, suspicious_moves


def _normalise_prices(prices: pd.DataFrame) -> pd.DataFrame:
    clean = prices.copy()
    clean["date"] = pd.to_datetime(clean["date"], errors="coerce")
    clean["ticker"] = clean["ticker"].astype("string").str.upper()

    numeric_columns = ["open", "high", "low", "close", "volume", "traded_value"]
    for column in numeric_columns:
        clean[column] = pd.to_numeric(clean[column], errors="coerce")

    return clean


def _append_dataset_summary(rows: list[dict[str, object]], prices: pd.DataFrame) -> None:
    rows.append(
        _row(
            section="summary",
            check="dataset_rows",
            issue_count=len(prices),
            trading_day_count=prices["date"].nunique(dropna=True),
            first_date=_format_date(prices["date"].min()),
            last_date=_format_date(prices["date"].max()),
            notes=f"unique_tickers={prices['ticker'].nunique(dropna=True)}",
        )
    )


def _append_ticker_coverage(rows: list[dict[str, object]], prices: pd.DataFrame) -> None:
    sorted_prices = prices.dropna(subset=["ticker"]).sort_values(["ticker", "date"], kind="stable")
    for ticker, group in sorted_prices.groupby("ticker", dropna=False):
        rows.append(
            _row(
                section="coverage",
                check="trading_day_count",
                ticker=ticker,
                issue_count=0,
                trading_day_count=group["date"].nunique(dropna=True),
                first_date=_format_date(group["date"].min()),
                last_date=_format_date(group["date"].max()),
            )
        )


def _append_missing_value_checks(rows: list[dict[str, object]], prices: pd.DataFrame) -> None:
    for column in REQUIRED_COLUMNS:
        missing_count = int(prices[column].isna().sum())
        rows.append(
            _row(
                section="missing_values",
                check="missing_values",
                column=column,
                issue_count=missing_count,
            )
        )


def _append_price_value_checks(rows: list[dict[str, object]], prices: pd.DataFrame) -> None:
    for column in PRICE_COLUMNS:
        mask = prices[column] <= 0
        rows.append(
            _row(
                section="price_integrity",
                check="price_less_or_equal_zero",
                column=column,
                issue_count=int(mask.sum()),
                first_date=_format_date(prices.loc[mask, "date"].min()),
                last_date=_format_date(prices.loc[mask, "date"].max()),
                min_value=_round_or_blank(prices[column].min()),
                max_value=_round_or_blank(prices[column].max()),
            )
        )


def _append_range_checks(rows: list[dict[str, object]], prices: pd.DataFrame) -> None:
    checks = {
        "high_less_than_low": prices["high"] < prices["low"],
        "open_outside_high_low": (prices["open"] < prices["low"]) | (prices["open"] > prices["high"]),
        "close_outside_high_low": (prices["close"] < prices["low"]) | (prices["close"] > prices["high"]),
    }
    for check_name, mask in checks.items():
        rows.append(
            _row(
                section="price_integrity",
                check=check_name,
                issue_count=int(mask.sum()),
                first_date=_format_date(prices.loc[mask, "date"].min()),
                last_date=_format_date(prices.loc[mask, "date"].max()),
            )
        )


def _append_duplicate_checks(rows: list[dict[str, object]], prices: pd.DataFrame) -> None:
    mask = prices.duplicated(["date", "ticker"], keep=False)
    rows.append(
        _row(
            section="duplicates",
            check="duplicate_date_ticker",
            issue_count=int(mask.sum()),
            first_date=_format_date(prices.loc[mask, "date"].min()),
            last_date=_format_date(prices.loc[mask, "date"].max()),
        )
    )


def _find_suspicious_moves(prices: pd.DataFrame, return_threshold: float) -> pd.DataFrame:
    clean = prices.dropna(subset=["date", "ticker", "close"]).copy()
    clean = clean.sort_values(["ticker", "date"], kind="stable").reset_index(drop=True)
    clean["previous_close"] = clean.groupby("ticker")["close"].shift(1)
    clean["daily_return"] = clean["close"] / clean["previous_close"] - 1

    mask = clean["daily_return"].abs() > return_threshold
    suspicious = clean.loc[mask, ["date", "ticker", "previous_close", "close", "daily_return"]].copy()
    suspicious["date"] = suspicious["date"].dt.strftime("%Y-%m-%d")
    suspicious["previous_close"] = suspicious["previous_close"].round(4)
    suspicious["close"] = suspicious["close"].round(4)
    suspicious["daily_return"] = suspicious["daily_return"].round(6)
    return suspicious.sort_values(["date", "ticker"], kind="stable").reset_index(drop=True)


def _append_suspicious_move_summary(
    rows: list[dict[str, object]],
    suspicious_moves: pd.DataFrame,
    return_threshold: float,
) -> None:
    rows.append(
        _row(
            section="returns",
            check="suspicious_daily_return",
            issue_count=len(suspicious_moves),
            first_date=suspicious_moves["date"].min() if not suspicious_moves.empty else "",
            last_date=suspicious_moves["date"].max() if not suspicious_moves.empty else "",
            min_value=_round_or_blank(suspicious_moves["daily_return"].min()),
            max_value=_round_or_blank(suspicious_moves["daily_return"].max()),
            notes=f"threshold=+/-{return_threshold:.2%}",
        )
    )

    for ticker, group in suspicious_moves.groupby("ticker", dropna=False):
        rows.append(
            _row(
                section="returns",
                check="suspicious_daily_return_by_ticker",
                ticker=ticker,
                issue_count=len(group),
                first_date=group["date"].min(),
                last_date=group["date"].max(),
                min_value=_round_or_blank(group["daily_return"].min()),
                max_value=_round_or_blank(group["daily_return"].max()),
                notes=f"threshold=+/-{return_threshold:.2%}",
            )
        )


def _row(
    section: str,
    check: str,
    ticker: object = "",
    column: str = "",
    issue_count: int = 0,
    trading_day_count: object = "",
    first_date: object = "",
    last_date: object = "",
    min_value: object = "",
    max_value: object = "",
    notes: str = "",
) -> dict[str, object]:
    return {
        "section": section,
        "check": check,
        "ticker": ticker,
        "column": column,
        "issue_count": issue_count,
        "trading_day_count": trading_day_count,
        "first_date": first_date,
        "last_date": last_date,
        "min_value": min_value,
        "max_value": max_value,
        "notes": notes,
    }


def _format_date(value: object) -> str:
    if pd.isna(value):
        return ""
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _round_or_blank(value: object, digits: int = 6) -> object:
    if pd.isna(value):
        return ""
    return round(float(value), digits)
