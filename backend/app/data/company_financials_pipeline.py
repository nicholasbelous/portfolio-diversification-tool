import argparse
import json
from pathlib import Path
from typing import List
import time

try:
    from app.db import get_database_url, redact_database_url
except ModuleNotFoundError:  # pragma: no cover - allows running from repo root
    from backend.app.db import get_database_url, redact_database_url

from app.services.financial_data_service import FinancialDataService


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_PATH = ROOT_DIR / "static" / "company_financials.json"
DEFAULT_SP500_REFERENCE_PATH = ROOT_DIR / "cache" / "sp500_reference.json"

def _load_tickers_from_sp500_reference(path: Path) -> List[str]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        return []
    return sorted([str(t).upper() for t in payload.keys() if str(t).strip()])


def _load_tickers_from_file(path: Path) -> List[str]:
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8")
    separators = [",", "\n", "\t", ";", " "]
    for sep in separators[1:]:
        raw = raw.replace(sep, separators[0])
    return sorted([tok.strip().upper() for tok in raw.split(",") if tok.strip()])


def _chunks(items: List[str], size: int) -> List[List[str]]:
    if size <= 0:
        return [items]
    return [items[i : i + size] for i in range(0, len(items), size)]


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
        "--from-sp500-reference",
        action="store_true",
        help="Load ticker list from cached S&P 500 reference file",
    )
    parser.add_argument(
        "--tickers-file",
        required=False,
        help="Path to file containing ticker symbols (comma/newline/space separated)",
    )
    parser.add_argument(
        "--sp500-reference-path",
        default=str(DEFAULT_SP500_REFERENCE_PATH),
        help="Path to S&P 500 reference JSON used with --from-sp500-reference",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Path to financial output JSON",
    )
    parser.add_argument(
        "--database-url",
        required=False,
        help="Postgres database URL. If omitted, uses DATABASE_URL env var.",
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
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of tickers processed (0 means no limit)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="Number of tickers per batch (lower helps avoid throttling)",
    )
    parser.add_argument(
        "--batch-sleep-seconds",
        type=float,
        default=2.0,
        help="Pause between batches to reduce provider throttling",
    )
    parser.add_argument(
        "--per-ticker-delay-seconds",
        type=float,
        default=0.1,
        help="Small delay between tickers to smooth request bursts",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    tickers = [t.upper() for t in (args.tickers or []) if t.strip()]
    if args.tickers_file:
        file_tickers = _load_tickers_from_file(Path(args.tickers_file).resolve())
        tickers = list(dict.fromkeys(tickers + file_tickers))
    if args.from_sp500_reference:
        sp500_tickers = _load_tickers_from_sp500_reference(Path(args.sp500_reference_path).resolve())
        tickers = list(dict.fromkeys(tickers + sp500_tickers))

    if not tickers:
        raise SystemExit(
            "No tickers provided. Use --tickers, --tickers-file, and/or --from-sp500-reference."
        )

    if args.limit and args.limit > 0:
        tickers = tickers[: args.limit]

    database_url = get_database_url(args.database_url)

    service = FinancialDataService(
        output_path=Path(args.output).resolve(),
        database_url=database_url,
        delay_seconds=max(0.0, args.delay_seconds),
        per_ticker_delay_seconds=max(0.0, args.per_ticker_delay_seconds),
        max_retries=max(1, args.max_retries),
        verbose=not args.quiet,
    )

    batches = _chunks(tickers, max(1, args.batch_size))
    aggregate_saved = {}
    aggregate_failed = {}
    aggregate_skipped: List[str] = []
    for idx, batch in enumerate(batches, start=1):
        print(f"Running batch {idx}/{len(batches)} with {len(batch)} ticker(s)")
        result = service.fetch_and_store(tickers=batch, force_refresh=args.force_refresh)
        aggregate_saved.update(result.saved)
        aggregate_failed.update(result.failed)
        aggregate_skipped.extend(result.skipped)
        if idx < len(batches) and args.batch_sleep_seconds > 0:
            time.sleep(args.batch_sleep_seconds)

    class AggregateResult:
        def __init__(self, saved, failed, skipped):
            self.saved = saved
            self.failed = failed
            self.skipped = skipped

    result = AggregateResult(
        saved=aggregate_saved,
        failed=aggregate_failed,
        skipped=sorted(set(aggregate_skipped)),
    )

    print(f"Saved {len(result.saved)} ticker snapshot(s) to {Path(args.output).resolve()}")
    print(f"Postgres database: {redact_database_url(database_url)}")
    print(f"DB snapshots total: {service.store.count_financial_snapshots()}")
    print(f"DB price_history rows total: {service.store.count_price_history_rows()}")
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
