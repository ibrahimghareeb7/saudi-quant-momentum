from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


PERIOD_COLUMNS = [
    "regime",
    "start_date",
    "end_date",
    "duration_days",
    "start_breadth",
    "end_breadth",
    "start_above_tasi_sma200",
    "end_above_tasi_sma200",
]
DIAGNOSTIC_COLUMNS = [
    "valid_days",
    "risk_on_days",
    "risk_off_days",
    "transition_count",
    "avg_risk_on_duration",
    "avg_risk_off_duration",
    "median_risk_on_duration",
    "median_risk_off_duration",
    "shortest_risk_on_duration",
    "shortest_risk_off_duration",
    "longest_risk_on_duration",
    "longest_risk_off_duration",
    "year_with_most_transitions",
    "very_short_regime_count_1_3_days",
]
REQUIRED_COLUMNS = [
    "date",
    "above_tasi_sma200",
    "breadth",
    "regime_valid",
    "regime",
]


@dataclass(frozen=True)
class RegimeDiagnosticsV2Config:
    regime_path: Path = Path("regime_v2.csv")
    periods_output_path: Path = Path("regime_periods_v2.csv")
    diagnostics_output_path: Path = Path("regime_diagnostics_v2.csv")


def run_regime_diagnostics_v2(
    config: RegimeDiagnosticsV2Config | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    config = config or RegimeDiagnosticsV2Config()
    _ensure_regime_v2_source(config.regime_path)
    _ensure_outputs_do_not_exist(config.periods_output_path, config.diagnostics_output_path)

    regime = load_regime_v2(config.regime_path)
    valid_regime = _valid_regime_rows(regime)
    periods = build_regime_periods(valid_regime)
    diagnostics = build_regime_diagnostics(valid_regime, periods)

    config.periods_output_path.parent.mkdir(parents=True, exist_ok=True)
    config.diagnostics_output_path.parent.mkdir(parents=True, exist_ok=True)
    periods.to_csv(config.periods_output_path, index=False)
    diagnostics.to_csv(config.diagnostics_output_path, index=False)
    return periods, diagnostics


def load_regime_v2(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Regime file not found: {path}")

    regime = pd.read_csv(path)
    missing = [column for column in REQUIRED_COLUMNS if column not in regime.columns]
    if missing:
        raise ValueError(f"Regime file is missing required columns: {', '.join(missing)}")
    return regime


def build_regime_periods(valid_regime: pd.DataFrame) -> pd.DataFrame:
    if valid_regime.empty:
        return pd.DataFrame(columns=PERIOD_COLUMNS)

    periods_source = valid_regime.copy()
    period_start = periods_source["regime"].ne(periods_source["regime"].shift()).fillna(True)
    periods_source["period_id"] = period_start.cumsum()

    rows: list[dict[str, object]] = []
    for _, group in periods_source.groupby("period_id", sort=True):
        first = group.iloc[0]
        last = group.iloc[-1]
        rows.append(
            {
                "regime": first["regime"],
                "start_date": first["date"].strftime("%Y-%m-%d"),
                "end_date": last["date"].strftime("%Y-%m-%d"),
                "duration_days": len(group),
                "start_breadth": round(float(first["breadth"]), 6),
                "end_breadth": round(float(last["breadth"]), 6),
                "start_above_tasi_sma200": bool(first["above_tasi_sma200"]),
                "end_above_tasi_sma200": bool(last["above_tasi_sma200"]),
            }
        )

    return pd.DataFrame(rows, columns=PERIOD_COLUMNS)


def build_regime_diagnostics(valid_regime: pd.DataFrame, periods: pd.DataFrame) -> pd.DataFrame:
    risk_on_periods = periods.loc[periods["regime"] == "Risk-On", "duration_days"]
    risk_off_periods = periods.loc[periods["regime"] == "Risk-Off", "duration_days"]
    transition_years = _transition_year_counts(periods)

    row = {
        "valid_days": len(valid_regime),
        "risk_on_days": int((valid_regime["regime"] == "Risk-On").sum()),
        "risk_off_days": int((valid_regime["regime"] == "Risk-Off").sum()),
        "transition_count": max(len(periods) - 1, 0),
        "avg_risk_on_duration": _round_stat(risk_on_periods.mean()),
        "avg_risk_off_duration": _round_stat(risk_off_periods.mean()),
        "median_risk_on_duration": _round_stat(risk_on_periods.median()),
        "median_risk_off_duration": _round_stat(risk_off_periods.median()),
        "shortest_risk_on_duration": _int_stat(risk_on_periods.min()),
        "shortest_risk_off_duration": _int_stat(risk_off_periods.min()),
        "longest_risk_on_duration": _int_stat(risk_on_periods.max()),
        "longest_risk_off_duration": _int_stat(risk_off_periods.max()),
        "year_with_most_transitions": _year_with_most_transitions(transition_years),
        "very_short_regime_count_1_3_days": int(periods["duration_days"].between(1, 3).sum()),
    }
    return pd.DataFrame([row], columns=DIAGNOSTIC_COLUMNS)


def transition_counts_by_year(periods: pd.DataFrame) -> pd.Series:
    return _transition_year_counts(periods)


def _valid_regime_rows(regime: pd.DataFrame) -> pd.DataFrame:
    clean = regime.copy()
    clean["date"] = pd.to_datetime(clean["date"], errors="coerce")
    clean["regime_valid"] = _to_bool(clean["regime_valid"])
    clean["above_tasi_sma200"] = _to_bool(clean["above_tasi_sma200"])
    clean["breadth"] = pd.to_numeric(clean["breadth"], errors="coerce")
    clean["regime"] = clean["regime"].astype("string")
    clean = clean.dropna(subset=["date", "regime", "breadth"])
    clean = clean.loc[clean["regime_valid"]].copy()
    clean = clean.loc[clean["regime"].isin(["Risk-On", "Risk-Off"])].copy()
    clean = clean.sort_values("date", kind="stable").reset_index(drop=True)
    return clean


def _transition_year_counts(periods: pd.DataFrame) -> pd.Series:
    if len(periods) <= 1:
        return pd.Series(dtype="int64")

    transition_starts = pd.to_datetime(periods.iloc[1:]["start_date"], errors="coerce")
    return transition_starts.dt.year.value_counts().sort_index()


def _year_with_most_transitions(transition_years: pd.Series) -> object:
    if transition_years.empty:
        return ""

    sorted_counts = transition_years.reset_index()
    sorted_counts.columns = ["year", "transition_count"]
    sorted_counts = sorted_counts.sort_values(["transition_count", "year"], ascending=[False, True])
    return int(sorted_counts.iloc[0]["year"])


def _to_bool(values: pd.Series) -> pd.Series:
    if values.dtype == bool:
        return values

    normalised = values.astype("string").str.strip().str.lower()
    return normalised.isin(["true", "1", "yes"])


def _round_stat(value: object) -> object:
    if pd.isna(value):
        return ""
    return round(float(value), 2)


def _int_stat(value: object) -> object:
    if pd.isna(value):
        return ""
    return int(value)


def _ensure_regime_v2_source(path: Path) -> None:
    if path.name != "regime_v2.csv":
        raise ValueError("Regime diagnostics v2 must use regime_v2.csv only.")


def _ensure_outputs_do_not_exist(*paths: Path) -> None:
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        joined = ", ".join(existing)
        raise FileExistsError(f"Refusing to overwrite existing output file(s): {joined}")
