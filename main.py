from __future__ import annotations

import argparse
from pathlib import Path
import sys

from saudi_quant.data.pipeline import DataPipelineConfig, run_pipeline
from saudi_quant.indicators.sma import SMA200Config, run_sma200_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Saudi Quant Momentum command line tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    data_parser = subparsers.add_parser("data", help="Build the Saudi EOD prices CSV.")
    add_data_args(data_parser)

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

    if args.command == "sma200":
        config = SMA200Config(prices_path=Path(args.prices), output_path=Path(args.output))
        result = run_sma200_pipeline(config)
        print(f"Wrote {len(result):,} rows to {config.output_path}")
        return

    raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
