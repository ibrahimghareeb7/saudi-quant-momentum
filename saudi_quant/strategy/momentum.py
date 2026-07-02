from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


LIQUIDITY_COLUMNS = [
    "date",
    "ticker",
    "close",
    "volume",
    "traded_value",
    "avg_traded_value_20d",
    "liquid",
]
RANKING_COLUMNS = [
    "date",
    "ticker",
    "close",
    "avg_traded_value_20d",
    "liquid",
    "rs_63d",
    "rs_126d",
    "volume_expansion",
    "distance_52w_high",
    "score",
    "rank",
]
TOP3_REVIEW_COLUMNS = ["date", "rank_1_ticker", "rank_2_ticker", "rank_3_ticker"]
RANKING_STABILITY_COLUMNS = [
    "ticker",
    "days_in_top3",
    "days_in_top5",
    "days_in_top10",
    "first_top3_date",
    "last_top3_date",
]
REQUIRED_COLUMNS = ["date", "ticker", "close", "volume"]
RANKING_REQUIRED_COLUMNS = ["date", "ticker", "rank"]


@dataclass(frozen=True)
class StrategyV2Config:
    prices_path: Path = Path("prices_v2.csv")
    liquidity_output_path: Path = Path("liquidity_v2.csv")
    ranking_output_path: Path = Path("momentum_ranking_v2.csv")
    liquidity_threshold: float = 20_000_000


@dataclass(frozen=True)
class RankingReviewV2Config:
    ranking_path: Path = Path("momentum_ranking_v2.csv")
    top3_output_path: Path = Path("top3_review_v2.csv")
    stability_output_path: Path = Path("ranking_stability_v2.csv")


def run_strategy_v2(config: StrategyV2Config | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    config = config or StrategyV2Config()
    _ensure_prices_v2_source(config.prices_path)
    _ensure_outputs_do_not_exist(config.liquidity_output_path, config.ranking_output_path)

    prices = load_strategy_prices(config.prices_path)
    liquidity = build_liquidity(prices, liquidity_threshold=config.liquidity_threshold)
    ranking = build_momentum_ranking(liquidity)

    config.liquidity_output_path.parent.mkdir(parents=True, exist_ok=True)
    config.ranking_output_path.parent.mkdir(parents=True, exist_ok=True)
    liquidity.to_csv(config.liquidity_output_path, index=False)
    ranking.to_csv(config.ranking_output_path, index=False)
    return liquidity, ranking


def run_ranking_review_v2(config: RankingReviewV2Config | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    config = config or RankingReviewV2Config()
    _ensure_ranking_v2_source(config.ranking_path)
    _ensure_outputs_do_not_exist(config.top3_output_path, config.stability_output_path)

    ranking = load_momentum_ranking(config.ranking_path)
    top3 = build_top3_review(ranking)
    stability = build_ranking_stability(ranking)

    config.top3_output_path.parent.mkdir(parents=True, exist_ok=True)
    config.stability_output_path.parent.mkdir(parents=True, exist_ok=True)
    top3.to_csv(config.top3_output_path, index=False)
    stability.to_csv(config.stability_output_path, index=False)
    return top3, stability


def load_strategy_prices(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Prices file not found: {path}")

    prices = pd.read_csv(path)
    missing = [column for column in REQUIRED_COLUMNS if column not in prices.columns]
    if missing:
        raise ValueError(f"Prices file is missing required columns: {', '.join(missing)}")

    return prices


def load_momentum_ranking(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Ranking file not found: {path}")

    ranking = pd.read_csv(path)
    missing = [column for column in RANKING_REQUIRED_COLUMNS if column not in ranking.columns]
    if missing:
        raise ValueError(f"Ranking file is missing required columns: {', '.join(missing)}")

    return ranking


def build_liquidity(prices: pd.DataFrame, liquidity_threshold: float = 20_000_000) -> pd.DataFrame:
    clean = _normalise_prices(prices)
    clean["traded_value"] = (clean["close"] * clean["volume"]).round(2)
    clean["avg_traded_value_20d"] = clean.groupby("ticker")["traded_value"].transform(
        lambda traded_value: traded_value.rolling(window=20, min_periods=20).mean()
    )
    clean["liquid"] = clean["avg_traded_value_20d"] >= liquidity_threshold

    liquidity = clean[LIQUIDITY_COLUMNS].copy()
    liquidity["date"] = liquidity["date"].dt.strftime("%Y-%m-%d")
    liquidity["close"] = liquidity["close"].round(4)
    liquidity["avg_traded_value_20d"] = liquidity["avg_traded_value_20d"].round(2)
    liquidity = liquidity.sort_values(["date", "ticker"], kind="stable").reset_index(drop=True)
    return liquidity


def build_momentum_ranking(liquidity: pd.DataFrame) -> pd.DataFrame:
    metrics = liquidity.copy()
    metrics["date"] = pd.to_datetime(metrics["date"], errors="coerce")
    metrics = metrics.sort_values(["ticker", "date"], kind="stable").reset_index(drop=True)

    grouped = metrics.groupby("ticker", group_keys=False)
    metrics["rs_63d"] = grouped["close"].transform(lambda close: close / close.shift(63) - 1)
    metrics["rs_126d"] = grouped["close"].transform(lambda close: close / close.shift(126) - 1)
    metrics["avg_volume_20d"] = grouped["volume"].transform(
        lambda volume: volume.rolling(window=20, min_periods=20).mean()
    )
    metrics["volume_expansion"] = metrics["volume"] / metrics["avg_volume_20d"]
    metrics["rolling_252d_high_close"] = grouped["close"].transform(
        lambda close: close.rolling(window=252, min_periods=252).max()
    )
    metrics["distance_52w_high"] = metrics["close"] / metrics["rolling_252d_high_close"] - 1

    ranking = metrics.loc[metrics["liquid"]].copy()
    ranking = ranking.dropna(subset=["rs_63d", "rs_126d", "volume_expansion", "distance_52w_high"])

    rank_columns = ["rs_126d", "rs_63d", "volume_expansion", "distance_52w_high"]
    for column in rank_columns:
        ranking[f"{column}_rank"] = ranking.groupby("date")[column].rank(pct=True, method="average")

    ranking["score"] = (
        0.40 * ranking["rs_126d_rank"]
        + 0.30 * ranking["rs_63d_rank"]
        + 0.20 * ranking["volume_expansion_rank"]
        + 0.10 * ranking["distance_52w_high_rank"]
    )
    ranking = ranking.sort_values(["date", "score", "ticker"], ascending=[True, False, True], kind="stable")
    ranking["rank"] = ranking.groupby("date").cumcount() + 1

    for column in ["rs_63d", "rs_126d", "volume_expansion", "distance_52w_high", "score"]:
        ranking[column] = ranking[column].round(6)
    ranking["close"] = ranking["close"].round(4)
    ranking["avg_traded_value_20d"] = ranking["avg_traded_value_20d"].round(2)
    ranking["date"] = ranking["date"].dt.strftime("%Y-%m-%d")

    return ranking[RANKING_COLUMNS].reset_index(drop=True)


def build_top3_review(ranking: pd.DataFrame) -> pd.DataFrame:
    clean = _normalise_ranking(ranking)
    top3 = clean.loc[clean["rank"].between(1, 3), ["date", "rank", "ticker"]].copy()
    top3["rank_column"] = "rank_" + top3["rank"].astype("int64").astype("string") + "_ticker"

    review = top3.pivot(index="date", columns="rank_column", values="ticker").reset_index()
    for column in TOP3_REVIEW_COLUMNS:
        if column not in review.columns:
            review[column] = ""

    review = review[TOP3_REVIEW_COLUMNS]
    review = review.sort_values("date", kind="stable").reset_index(drop=True)
    return review


def build_ranking_stability(ranking: pd.DataFrame) -> pd.DataFrame:
    clean = _normalise_ranking(ranking)
    rows: list[dict[str, object]] = []

    for ticker, group in clean.groupby("ticker", sort=True):
        top3 = group.loc[group["rank"] <= 3]
        rows.append(
            {
                "ticker": ticker,
                "days_in_top3": int((group["rank"] <= 3).sum()),
                "days_in_top5": int((group["rank"] <= 5).sum()),
                "days_in_top10": int((group["rank"] <= 10).sum()),
                "first_top3_date": top3["date"].min() if not top3.empty else "",
                "last_top3_date": top3["date"].max() if not top3.empty else "",
            }
        )

    return pd.DataFrame(rows, columns=RANKING_STABILITY_COLUMNS)


def _normalise_prices(prices: pd.DataFrame) -> pd.DataFrame:
    clean = prices.copy()
    clean["date"] = pd.to_datetime(clean["date"], errors="coerce")
    clean["ticker"] = clean["ticker"].astype("string").str.upper()
    clean["close"] = pd.to_numeric(clean["close"], errors="coerce")
    clean["volume"] = pd.to_numeric(clean["volume"], errors="coerce")
    clean = clean.dropna(subset=["date", "ticker", "close", "volume"])
    clean["volume"] = clean["volume"].round().astype("int64")
    clean = clean.sort_values(["ticker", "date"], kind="stable").reset_index(drop=True)
    return clean


def _normalise_ranking(ranking: pd.DataFrame) -> pd.DataFrame:
    clean = ranking.copy()
    clean["date"] = pd.to_datetime(clean["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    clean["ticker"] = clean["ticker"].astype("string").str.upper()
    clean["rank"] = pd.to_numeric(clean["rank"], errors="coerce")
    clean = clean.dropna(subset=["date", "ticker", "rank"])
    clean["rank"] = clean["rank"].astype("int64")
    clean = clean.sort_values(["date", "rank"], kind="stable").reset_index(drop=True)
    return clean


def _ensure_prices_v2_source(path: Path) -> None:
    if path.name != "prices_v2.csv":
        raise ValueError("The first strategy layer must use prices_v2.csv only.")


def _ensure_ranking_v2_source(path: Path) -> None:
    if path.name != "momentum_ranking_v2.csv":
        raise ValueError("Ranking review must use momentum_ranking_v2.csv only.")


def _ensure_outputs_do_not_exist(*paths: Path) -> None:
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        joined = ", ".join(existing)
        raise FileExistsError(f"Refusing to overwrite existing output file(s): {joined}")
