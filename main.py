from __future__ import annotations

import argparse
from pathlib import Path

from saudi_quant.data.pipeline import DataPipelineConfig, run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Saudi EOD prices CSV.")
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = DataPipelineConfig(
        output_path=Path(args.output),
        start=args.start,
        end=args.end,
        include_adjusted_close=args.include_adjusted_close,
    )
    result = run_pipeline(config)
    print(f"Wrote {len(result):,} rows to {config.output_path}")


if __name__ == "__main__":
    main()
