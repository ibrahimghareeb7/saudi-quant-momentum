from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from saudi_quant.data.adjustment_audit import audit_price_adjustments
from saudi_quant.data.quality import audit_prices, load_prices_for_audit
from saudi_quant.indicators.sma import calculate_sma200


@dataclass(frozen=True)
class V2PipelineConfig:
    prices_path: Path = Path("prices.csv")
    start_date: str = "2014-01-01"
    prices_output_path: Path = Path("prices_v2.csv")
    data_quality_report_output_path: Path = Path("data_quality_report_v2.csv")
    suspicious_moves_output_path: Path = Path("suspicious_price_moves_v2.csv")
    adjustment_audit_output_path: Path = Path("adjustment_audit_report_v2.csv")
    ticker_quality_summary_output_path: Path = Path("ticker_quality_summary_v2.csv")
    sma200_output_path: Path = Path("sma200_v2.csv")


def run_v2_pipeline(config: V2PipelineConfig | None = None) -> dict[Path, int]:
    config = config or V2PipelineConfig()
    output_paths = [
        config.prices_output_path,
        config.data_quality_report_output_path,
        config.suspicious_moves_output_path,
        config.adjustment_audit_output_path,
        config.ticker_quality_summary_output_path,
        config.sma200_output_path,
    ]
    _ensure_outputs_do_not_exist(output_paths)

    prices = load_prices_for_audit(config.prices_path)
    prices_v2 = build_prices_v2(prices, start_date=config.start_date)
    data_quality_report, suspicious_moves = audit_prices(prices_v2)
    adjustment_audit_report, ticker_quality_summary = audit_price_adjustments(prices_v2)
    sma200 = calculate_sma200(prices_v2)

    outputs = {
        config.prices_output_path: prices_v2,
        config.data_quality_report_output_path: data_quality_report,
        config.suspicious_moves_output_path: suspicious_moves,
        config.adjustment_audit_output_path: adjustment_audit_report,
        config.ticker_quality_summary_output_path: ticker_quality_summary,
        config.sma200_output_path: sma200,
    }

    for path, frame in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)

    return {path: len(frame) for path, frame in outputs.items()}


def build_prices_v2(prices: pd.DataFrame, start_date: str = "2014-01-01") -> pd.DataFrame:
    clean = prices.copy()
    clean["date"] = pd.to_datetime(clean["date"], errors="coerce")
    start = pd.Timestamp(start_date)
    clean = clean.loc[clean["date"] >= start].copy()
    clean["date"] = clean["date"].dt.strftime("%Y-%m-%d")
    clean = clean.sort_values(["date", "ticker"], kind="stable").reset_index(drop=True)
    return clean


def _ensure_outputs_do_not_exist(paths: list[Path]) -> None:
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        joined = ", ".join(existing)
        raise FileExistsError(f"Refusing to overwrite existing output file(s): {joined}")
