from __future__ import annotations

import argparse
from pathlib import Path
import sys

from saudi_quant.data.adjustment_audit import AdjustmentAuditConfig, run_adjustment_audit
from saudi_quant.data.pipeline import DataPipelineConfig, run_pipeline
from saudi_quant.data.quality import DataQualityConfig, run_data_quality_audit
from saudi_quant.data.v2_pipeline import V2PipelineConfig, run_v2_pipeline
from saudi_quant.indicators.sma import SMA200Config, run_sma200_pipeline
from saudi_quant.strategy.momentum import (
    RankingReviewV2Config,
    StrategyV2Config,
    run_ranking_review_v2,
    run_strategy_v2,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Saudi Quant Momentum command line tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    data_parser = subparsers.add_parser("data", help="Build the Saudi EOD prices CSV.")
    add_data_args(data_parser)

    quality_parser = subparsers.add_parser("data-quality", help="Audit prices.csv quality.")
    quality_parser.add_argument(
        "--prices",
        default="prices.csv",
        help="Input prices CSV path. Defaults to prices.csv.",
    )
    quality_parser.add_argument(
        "--report-output",
        default="data_quality_report.csv",
        help="Data quality report CSV path. Defaults to data_quality_report.csv.",
    )
    quality_parser.add_argument(
        "--moves-output",
        default="suspicious_price_moves.csv",
        help="Suspicious daily moves CSV path. Defaults to suspicious_price_moves.csv.",
    )
    quality_parser.add_argument(
        "--return-threshold",
        default=0.15,
        type=float,
        help="Absolute daily return threshold for suspicious moves. Defaults to 0.15.",
    )

    adjustment_parser = subparsers.add_parser(
        "adjustment-audit",
        help="Audit likely price adjustment and corporate action issues.",
    )
    adjustment_parser.add_argument(
        "--prices",
        default="prices.csv",
        help="Input prices CSV path. Defaults to prices.csv.",
    )
    adjustment_parser.add_argument(
        "--report-output",
        default="adjustment_audit_report.csv",
        help="Adjustment audit CSV path. Defaults to adjustment_audit_report.csv.",
    )
    adjustment_parser.add_argument(
        "--summary-output",
        default="ticker_quality_summary.csv",
        help="Ticker quality summary CSV path. Defaults to ticker_quality_summary.csv.",
    )
    adjustment_parser.add_argument(
        "--return-threshold",
        default=0.15,
        type=float,
        help="Absolute daily return threshold for suspicious moves. Defaults to 0.15.",
    )
    adjustment_parser.add_argument(
        "--cluster-window",
        default=5,
        type=int,
        help="Trading-day gap for grouping suspicious moves. Defaults to 5.",
    )

    v2_parser = subparsers.add_parser(
        "v2-post-2014",
        help="Generate post-2014 prices and audit outputs without modifying prices.csv.",
    )
    v2_parser.add_argument(
        "--prices",
        default="prices.csv",
        help="Input prices CSV path. Defaults to prices.csv.",
    )
    v2_parser.add_argument(
        "--start-date",
        default="2014-01-01",
        help="Inclusive start date for v2. Defaults to 2014-01-01.",
    )

    sma_parser = subparsers.add_parser("sma200", help="Build the SMA200 indicator CSV.")
    sma_parser.add_argument(
        "--prices",
        default="prices.csv",
        help="Input prices CSV path. Defaults to prices.csv.",
    )
    sma_parser.add_argument(
        "--output",
        default="sma200.csv",
        help="SMA200 output CSV path. Defaults to sma200.csv.",
    )

    strategy_parser = subparsers.add_parser(
        "strategy-v2",
        help="Build liquidity and momentum ranking files from prices_v2.csv only.",
    )
    strategy_parser.add_argument(
        "--prices",
        default="prices_v2.csv",
        help="Input v2 prices CSV path. Defaults to prices_v2.csv.",
    )
    strategy_parser.add_argument(
        "--liquidity-output",
        default="liquidity_v2.csv",
        help="Liquidity output CSV path. Defaults to liquidity_v2.csv.",
    )
    strategy_parser.add_argument(
        "--ranking-output",
        default="momentum_ranking_v2.csv",
        help="Momentum ranking output CSV path. Defaults to momentum_ranking_v2.csv.",
    )
    strategy_parser.add_argument(
        "--liquidity-threshold",
        default=20_000_000,
        type=float,
        help="Minimum 20-day average traded value. Defaults to 20,000,000.",
    )

    review_parser = subparsers.add_parser(
        "ranking-review-v2",
        help="Build review files from momentum_ranking_v2.csv.",
    )
    review_parser.add_argument(
        "--ranking",
        default="momentum_ranking_v2.csv",
        help="Input ranking CSV path. Defaults to momentum_ranking_v2.csv.",
    )
    review_parser.add_argument(
        "--top3-output",
        default="top3_review_v2.csv",
        help="Top-3 review CSV path. Defaults to top3_review_v2.csv.",
    )
    review_parser.add_argument(
        "--stability-output",
        default="ranking_stability_v2.csv",
        help="Ranking stability CSV path. Defaults to ranking_stability_v2.csv.",
    )

    return parser


def add_data_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--output",
        default="prices.csv",
        help="CSV output path. Defaults to prices.csv in the project root.",
    )
    parser.add_argument(
        "--start",
        default="2010-01-01",
        help="Start date in YYYY-MM-DD format. Defaults to 2010-01-01.",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="Optional end date in YYYY-MM-DD format. Yahoo treats this as exclusive. Defaults to today to avoid partial EOD rows.",
    )
    parser.add_argument(
        "--include-adjusted-close",
        action="store_true",
        help="Include adjusted_close in the CSV when the data provider returns it.",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    raw_args = list(sys.argv[1:] if argv is None else argv)

    if not raw_args or raw_args[0].startswith("-"):
        raw_args = ["data", *raw_args]

    parser = build_parser()
    return parser.parse_args(raw_args)


def main() -> None:
    args = parse_args()

    if args.command == "data":
        config = DataPipelineConfig(
            output_path=Path(args.output),
            start=args.start,
            end=args.end,
            include_adjusted_close=args.include_adjusted_close,
        )
        result = run_pipeline(config)
        print(f"Wrote {len(result):,} rows to {config.output_path}")
        return

    if args.command == "data-quality":
        config = DataQualityConfig(
            prices_path=Path(args.prices),
            report_output_path=Path(args.report_output),
            moves_output_path=Path(args.moves_output),
            return_threshold=args.return_threshold,
        )
        report, moves = run_data_quality_audit(config)
        print(f"Wrote {len(report):,} rows to {config.report_output_path}")
        print(f"Wrote {len(moves):,} rows to {config.moves_output_path}")
        return

    if args.command == "adjustment-audit":
        config = AdjustmentAuditConfig(
            prices_path=Path(args.prices),
            report_output_path=Path(args.report_output),
            summary_output_path=Path(args.summary_output),
            return_threshold=args.return_threshold,
            cluster_window=args.cluster_window,
        )
        report, summary = run_adjustment_audit(config)
        print(f"Wrote {len(report):,} rows to {config.report_output_path}")
        print(f"Wrote {len(summary):,} rows to {config.summary_output_path}")
        return

    if args.command == "v2-post-2014":
        config = V2PipelineConfig(prices_path=Path(args.prices), start_date=args.start_date)
        outputs = run_v2_pipeline(config)
        for path, row_count in outputs.items():
            print(f"Wrote {row_count:,} rows to {path}")
        return

    if args.command == "sma200":
        config = SMA200Config(prices_path=Path(args.prices), output_path=Path(args.output))
        result = run_sma200_pipeline(config)
        print(f"Wrote {len(result):,} rows to {config.output_path}")
        return

    if args.command == "strategy-v2":
        config = StrategyV2Config(
            prices_path=Path(args.prices),
            liquidity_output_path=Path(args.liquidity_output),
            ranking_output_path=Path(args.ranking_output),
            liquidity_threshold=args.liquidity_threshold,
        )
        liquidity, ranking = run_strategy_v2(config)
        print(f"Wrote {len(liquidity):,} rows to {config.liquidity_output_path}")
        print(f"Wrote {len(ranking):,} rows to {config.ranking_output_path}")
        return

    if args.command == "ranking-review-v2":
        config = RankingReviewV2Config(
            ranking_path=Path(args.ranking),
            top3_output_path=Path(args.top3_output),
            stability_output_path=Path(args.stability_output),
        )
        top3, stability = run_ranking_review_v2(config)
        print(f"Wrote {len(top3):,} rows to {config.top3_output_path}")
        print(f"Wrote {len(stability):,} rows to {config.stability_output_path}")
        return

    raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
