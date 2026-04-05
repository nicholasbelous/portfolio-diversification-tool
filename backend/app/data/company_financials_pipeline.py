import argparse
import json
from pathlib import Path
from typing import List

from app.services.financial_data_service import FinancialDataService


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_METADATA_PATH = ROOT_DIR / "static" / "company_metadata.json"
DEFAULT_OUTPUT_PATH = ROOT_DIR / "static" / "company_financials.json"
DEFAULT_DB_PATH = ROOT_DIR / "static" / "portfolio_data.db"


def _load_tickers_from_metadata(path: Path) -> List[str]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        return []
    return sorted([str(t).upper() for t in payload.keys() if str(t).strip()])


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch financial snapshots and store them in company_financials.json"
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        required=False,
        help="Ticker symbols (example: AAPL MSFT NVDA)",
    )
    parser.add_argument(
        "--from-metadata-file",
        action="store_true",
        help="Load ticker list from company_metadata.json keys",
    )
    parser.add_argument(
        "--metadata-path",
        default=str(DEFAULT_METADATA_PATH),
        help="Path to metadata JSON file used with --from-metadata-file",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Path to financial output JSON",
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="Path to SQLite database file",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Refresh data even for tickers already in output JSON",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=1.0,
        help="Delay/backoff base in seconds",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=4,
        help="Max retries per provider request",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Disable live progress logs",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    tickers = [t.upper() for t in (args.tickers or []) if t.strip()]
    if args.from_metadata_file:
        metadata_tickers = _load_tickers_from_metadata(Path(args.metadata_path).resolve())
        tickers = list(dict.fromkeys(tickers + metadata_tickers))

    if not tickers:
        raise SystemExit("No tickers provided. Use --tickers and/or --from-metadata-file.")

    service = FinancialDataService(
        output_path=Path(args.output).resolve(),
        db_path=Path(args.db_path).resolve(),
        delay_seconds=max(0.0, args.delay_seconds),
        max_retries=max(1, args.max_retries),
        verbose=not args.quiet,
    )

    result = service.fetch_and_store(tickers=tickers, force_refresh=args.force_refresh)

    print(f"Saved {len(result.saved)} ticker snapshot(s) to {Path(args.output).resolve()}")
    print(f"SQLite database: {Path(args.db_path).resolve()}")
    if result.saved:
        print("Saved:", ", ".join(sorted(result.saved.keys())))
    if result.skipped:
        print("Skipped:", ", ".join(sorted(result.skipped)))
    if result.failed:
        print("Failed:")
        for ticker, msg in sorted(result.failed.items()):
            print(f"  - {ticker}: {msg}")


if __name__ == "__main__":
    main()
