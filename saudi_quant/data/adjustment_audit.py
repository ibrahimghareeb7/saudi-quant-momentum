from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from saudi_quant.data.quality import load_prices_for_audit


AUDIT_COLUMNS = [
    "ticker",
    "date",
    "close",
    "prev_close",
    "daily_return",
    "next_1d_return",
    "next_3d_return",
    "suspected_reason",
]
SUMMARY_COLUMNS = [
    "ticker",
    "row_count",
    "suspicious_moves_count",
    "close_outside_range_count",
    "first_date",
    "last_date",
    "quality_status",
]


@dataclass(frozen=True)
class AdjustmentAuditConfig:
    prices_path: Path = Path("prices.csv")
    report_output_path: Path = Path("adjustment_audit_report.csv")
    summary_output_path: Path = Path("ticker_quality_summary.csv")
    return_threshold: float = 0.15
    cluster_window: int = 5


def run_adjustment_audit(config: AdjustmentAuditConfig | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    config = config or AdjustmentAuditConfig()
    _ensure_outputs_do_not_exist(config.report_output_path, config.summary_output_path)

    prices = load_prices_for_audit(config.prices_path)
    audit_report, ticker_summary = audit_price_adjustments(
        prices,
        return_threshold=config.return_threshold,
        cluster_window=config.cluster_window,
    )

    config.report_output_path.parent.mkdir(parents=True, exist_ok=True)
    config.summary_output_path.parent.mkdir(parents=True, exist_ok=True)
    audit_report.to_csv(config.report_output_path, index=False)
    ticker_summary.to_csv(config.summary_output_path, index=False)
    return audit_report, ticker_summary


def audit_price_adjustments(
    prices: pd.DataFrame,
    return_threshold: float = 0.15,
    cluster_window: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if return_threshold <= 0:
        raise ValueError("return_threshold must be greater than zero")
    if cluster_window <= 0:
        raise ValueError("cluster_window must be greater than zero")

    clean = _normalise_prices(prices)
    enriched = _add_return_columns(clean)
    suspicious = _find_suspicious_moves(
        enriched,
        return_threshold=return_threshold,
        cluster_window=cluster_window,
    )
    summary = _build_ticker_summary(clean, suspicious)
    return suspicious[AUDIT_COLUMNS], summary[SUMMARY_COLUMNS]


def _normalise_prices(prices: pd.DataFrame) -> pd.DataFrame:
    clean = prices.copy()
    clean["date"] = pd.to_datetime(clean["date"], errors="coerce")
    clean["ticker"] = clean["ticker"].astype("string").str.upper()

    for column in ["open", "high", "low", "close", "volume", "traded_value"]:
        clean[column] = pd.to_numeric(clean[column], errors="coerce")

    clean = clean.dropna(subset=["date", "ticker", "close"])
    clean = clean.sort_values(["ticker", "date"], kind="stable").reset_index(drop=True)
    clean["trading_index"] = clean.groupby("ticker").cumcount()
    return clean


def _add_return_columns(prices: pd.DataFrame) -> pd.DataFrame:
    enriched = prices.copy()
    grouped = enriched.groupby("ticker", group_keys=False)

    enriched["prev_close"] = grouped["close"].shift(1)
    enriched["daily_return"] = enriched["close"] / enriched["prev_close"] - 1
    enriched["next_1d_return"] = grouped["close"].shift(-1) / enriched["close"] - 1
    enriched["next_3d_return"] = grouped["close"].shift(-3) / enriched["close"] - 1
    return enriched


def _find_suspicious_moves(
    prices: pd.DataFrame,
    return_threshold: float,
    cluster_window: int,
) -> pd.DataFrame:
    suspicious = prices.loc[prices["daily_return"].abs() > return_threshold].copy()
    if suspicious.empty:
        return pd.DataFrame(columns=AUDIT_COLUMNS)

    suspicious["cluster_id"] = _assign_cluster_ids(suspicious, cluster_window=cluster_window)
    cluster_sizes = suspicious.groupby(["ticker", "cluster_id"])["cluster_id"].transform("size")
    suspicious["cluster_size"] = cluster_sizes
    suspicious["suspected_reason"] = suspicious.apply(
        lambda row: _suspected_reason(row, return_threshold=return_threshold),
        axis=1,
    )

    suspicious["date"] = suspicious["date"].dt.strftime("%Y-%m-%d")
    for column in ["close", "prev_close"]:
        suspicious[column] = suspicious[column].round(4)
    for column in ["daily_return", "next_1d_return", "next_3d_return"]:
        suspicious[column] = suspicious[column].round(6)

    return suspicious.sort_values(["ticker", "date"], kind="stable").reset_index(drop=True)


def _assign_cluster_ids(suspicious: pd.DataFrame, cluster_window: int) -> pd.Series:
    cluster_ids = pd.Series(index=suspicious.index, dtype="int64")

    for _, group in suspicious.groupby("ticker", sort=False):
        sorted_group = group.sort_values("trading_index", kind="stable")
        cluster_id = 0
        previous_index: int | None = None

        for row_index, trading_index in sorted_group["trading_index"].items():
            current_index = int(trading_index)
            if previous_index is not None and current_index - previous_index > cluster_window:
                cluster_id += 1
            cluster_ids.loc[row_index] = cluster_id
            previous_index = current_index

    return cluster_ids


def _suspected_reason(row: pd.Series, return_threshold: float) -> str:
    reasons: list[str] = []

    next_1d_reverses = _is_reversal(row["daily_return"], row["next_1d_return"], return_threshold)
    next_3d_reverses = _is_reversal(row["daily_return"], row["next_3d_return"], return_threshold)

    if next_1d_reverses:
        reasons.append("likely_adjustment_issue_reversal_1d")
    elif next_3d_reverses:
        reasons.append("likely_adjustment_issue_reversal_3d")

    if int(row["cluster_size"]) > 1:
        reasons.append("clustered_within_5_trading_days")

    if not reasons:
        reasons.append("isolated_suspicious_move")

    return "|".join(reasons)


def _is_reversal(daily_return: object, forward_return: object, return_threshold: float) -> bool:
    if pd.isna(daily_return) or pd.isna(forward_return):
        return False

    daily = float(daily_return)
    forward = float(forward_return)
    return daily * forward < 0 and abs(forward) > return_threshold


def _build_ticker_summary(prices: pd.DataFrame, suspicious: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    suspicious_counts = suspicious.groupby("ticker").size().to_dict() if not suspicious.empty else {}
    likely_counts = _likely_adjustment_counts(suspicious)

    for ticker, group in prices.groupby("ticker", sort=True):
        close_outside_range_count = int(((group["close"] < group["low"]) | (group["close"] > group["high"])).sum())
        suspicious_moves_count = int(suspicious_counts.get(ticker, 0))
        likely_adjustment_count = int(likely_counts.get(ticker, 0))

        rows.append(
            {
                "ticker": ticker,
                "row_count": len(group),
                "suspicious_moves_count": suspicious_moves_count,
                "close_outside_range_count": close_outside_range_count,
                "first_date": group["date"].min().strftime("%Y-%m-%d"),
                "last_date": group["date"].max().strftime("%Y-%m-%d"),
                "quality_status": _quality_status(
                    suspicious_moves_count=suspicious_moves_count,
                    close_outside_range_count=close_outside_range_count,
                    likely_adjustment_count=likely_adjustment_count,
                ),
            }
        )

    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def _likely_adjustment_counts(suspicious: pd.DataFrame) -> dict[str, int]:
    if suspicious.empty:
        return {}

    mask = suspicious["suspected_reason"].str.contains("likely_adjustment_issue", regex=False)
    return suspicious.loc[mask].groupby("ticker").size().to_dict()


def _quality_status(
    suspicious_moves_count: int,
    close_outside_range_count: int,
    likely_adjustment_count: int,
) -> str:
    if close_outside_range_count > 0 or likely_adjustment_count > 0 or suspicious_moves_count >= 5:
        return "unreliable"
    if suspicious_moves_count > 0:
        return "usable_with_warnings"
    return "clean"


def _ensure_outputs_do_not_exist(*paths: Path) -> None:
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        joined = ", ".join(existing)
        raise FileExistsError(f"Refusing to overwrite existing output file(s): {joined}")
