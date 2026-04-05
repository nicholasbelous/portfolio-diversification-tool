import argparse
import json
import time
from io import StringIO
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import requests
import yfinance as yf


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_PATH = ROOT_DIR / "static" / "company_metadata.json"
DEFAULT_CACHE_PATH = ROOT_DIR / "cache" / "ticker_info_cache.json"
DEFAULT_SP500_CACHE_PATH = ROOT_DIR / "cache" / "sp500_reference.json"
SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
DEFAULT_SEED_TICKERS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOGL",
    "AMZN",
    "META",
    "BRK-B",
    "JPM",
    "XOM",
    "JNJ",
    "UNH",
    "PG",
    "HD",
    "V",
    "MA",
]
DEFAULT_FALLBACK_REFERENCE = {
    "AAPL": {"name": "Apple Inc.", "sector": "Technology", "industry": "Consumer Electronics", "country": "United States"},
    "MSFT": {"name": "Microsoft Corporation", "sector": "Technology", "industry": "Software - Infrastructure", "country": "United States"},
    "NVDA": {"name": "NVIDIA Corporation", "sector": "Technology", "industry": "Semiconductors", "country": "United States"},
    "GOOGL": {"name": "Alphabet Inc.", "sector": "Communication Services", "industry": "Internet Content & Information", "country": "United States"},
    "AMZN": {"name": "Amazon.com, Inc.", "sector": "Consumer Discretionary", "industry": "Internet Retail", "country": "United States"},
    "META": {"name": "Meta Platforms, Inc.", "sector": "Communication Services", "industry": "Internet Content & Information", "country": "United States"},
    "BRK-B": {"name": "Berkshire Hathaway Inc.", "sector": "Financials", "industry": "Insurance - Diversified", "country": "United States"},
    "JPM": {"name": "JPMorgan Chase & Co.", "sector": "Financials", "industry": "Banks - Diversified", "country": "United States"},
    "XOM": {"name": "Exxon Mobil Corporation", "sector": "Energy", "industry": "Oil & Gas Integrated", "country": "United States"},
    "JNJ": {"name": "Johnson & Johnson", "sector": "Health Care", "industry": "Drug Manufacturers - General", "country": "United States"},
    "UNH": {"name": "UnitedHealth Group Incorporated", "sector": "Health Care", "industry": "Healthcare Plans", "country": "United States"},
    "PG": {"name": "The Procter & Gamble Company", "sector": "Consumer Staples", "industry": "Household & Personal Products", "country": "United States"},
    "HD": {"name": "The Home Depot, Inc.", "sector": "Consumer Discretionary", "industry": "Home Improvement Retail", "country": "United States"},
    "V": {"name": "Visa Inc.", "sector": "Financials", "industry": "Credit Services", "country": "United States"},
    "MA": {"name": "Mastercard Incorporated", "sector": "Financials", "industry": "Credit Services", "country": "United States"},
}


@dataclass
class PipelineResult:
    saved: Dict[str, Dict[str, Any]]
    failed: Dict[str, str]


class CompanyMetadataPipeline:
    """
    Fetches company metadata from Yahoo Finance and stores it in JSON.
    """

    def __init__(
        self,
        output_path: Path = DEFAULT_OUTPUT_PATH,
        cache_path: Path = DEFAULT_CACHE_PATH,
        sp500_cache_path: Path = DEFAULT_SP500_CACHE_PATH,
        delay_seconds: float = 1.0,
        max_retries: int = 4,
        verbose: bool = True,
    ):
        self.output_path = output_path
        self.cache_path = cache_path
        self.sp500_cache_path = sp500_cache_path
        self.delay_seconds = delay_seconds
        self.max_retries = max_retries
        self.verbose = verbose
        self._sp500_reference: Dict[str, Dict[str, Any]] | None = None
        self._yahoo_rate_limited = False

    def _log(self, message: str) -> None:
        if self.verbose:
            print(message, flush=True)

    @staticmethod
    def _risk_profile_from_beta(beta: Any) -> str:
        if beta is None:
            return "medium"
        try:
            value = float(beta)
        except (TypeError, ValueError):
            return "medium"

        if value < 0.9:
            return "low"
        if value <= 1.2:
            return "medium"
        return "high"

    @staticmethod
    def _growth_profile_from_metrics(info: Dict[str, Any]) -> str:
        growth = info.get("revenueGrowth")
        if growth is None:
            growth = info.get("earningsGrowth")

        try:
            growth_value = float(growth)
        except (TypeError, ValueError):
            growth_value = None

        if growth_value is not None:
            if growth_value >= 0.15:
                return "high"
            if growth_value >= 0.03:
                return "medium"
            return "low"

        market_cap = info.get("marketCap")
        try:
            cap_value = float(market_cap)
        except (TypeError, ValueError):
            cap_value = None

        if cap_value is None:
            return "medium"
        if cap_value >= 100_000_000_000:
            return "medium"
        if cap_value >= 10_000_000_000:
            return "high"
        return "low"

    @staticmethod
    def _build_record(ticker: str, info: Dict[str, Any]) -> Dict[str, Any]:
        beta = info.get("beta")
        sector = info.get("sector") or "Unknown"
        industry = info.get("industry") or "Unknown"

        return {
            "name": info.get("shortName") or info.get("longName") or ticker,
            "sector": sector,
            "industry": industry,
            "country": info.get("country") or "Unknown",
            "market_cap": info.get("marketCap"),
            "beta": beta,
            "risk_profile": CompanyMetadataPipeline._risk_profile_from_beta(beta),
            "growth_profile": CompanyMetadataPipeline._growth_profile_from_metrics(info),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "source": "yfinance",
        }

    def _load_existing(self) -> Dict[str, Dict[str, Any]]:
        if not self.output_path.exists():
            return {}
        with open(self.output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        return {}

    def _load_cache(self) -> Dict[str, Dict[str, Any]]:
        if not self.cache_path.exists():
            return {}
        with open(self.cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        return {}

    @staticmethod
    def _to_jsonable(value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, dict):
            return {str(k): CompanyMetadataPipeline._to_jsonable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [CompanyMetadataPipeline._to_jsonable(v) for v in value]
        return str(value)

    def _save_cache(self, cache: Dict[str, Dict[str, Any]]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, sort_keys=True)

    def _save_output(self, data: Dict[str, Dict[str, Any]]) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)

    def _fetch_info_with_retry(self, ticker: str) -> Dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            attempt_num = attempt + 1
            try:
                self._log(f"[{ticker}] request attempt {attempt_num}/{self.max_retries}")
                info = yf.Ticker(ticker).info
                if not info or info.get("quoteType") is None:
                    raise ValueError("Ticker not found or no company data returned")
                self._log(f"[{ticker}] fetch success")
                return info
            except Exception as exc:
                last_exc = exc
                if "Too Many Requests" in str(exc):
                    self._yahoo_rate_limited = True
                    raise RuntimeError("Yahoo rate limited; switching to fallback mode") from exc
                wait_seconds = self.delay_seconds * (2**attempt)
                self._log(
                    f"[{ticker}] attempt {attempt_num} failed: {exc}. "
                    f"retrying in {wait_seconds:.1f}s"
                )
                time.sleep(wait_seconds)
        raise RuntimeError(f"Failed after retries: {last_exc}")

    def _normalize_symbol(self, symbol: str) -> str:
        return symbol.upper().replace(".", "-").strip()

    def _load_sp500_reference(self) -> Dict[str, Dict[str, Any]]:
        if self._sp500_reference is not None:
            return self._sp500_reference

        if self.sp500_cache_path.exists():
            try:
                with open(self.sp500_cache_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if isinstance(cached, dict) and cached:
                    self._sp500_reference = cached
                    self._log("[fallback] loaded S&P 500 reference from local cache")
                    return cached
            except Exception:
                pass

        self._log("[fallback] downloading S&P 500 reference table")
        response = requests.get(
            SP500_WIKI_URL,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
        )
        response.raise_for_status()
        table = pd.read_html(StringIO(response.text))[0]

        reference: Dict[str, Dict[str, Any]] = {}
        for _, row in table.iterrows():
            symbol = self._normalize_symbol(str(row["Symbol"]))
            reference[symbol] = {
                "name": str(row["Security"]),
                "sector": str(row["GICS Sector"]),
                "industry": str(row["GICS Sub-Industry"]),
                "country": "United States",
            }

        self.sp500_cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.sp500_cache_path, "w", encoding="utf-8") as f:
            json.dump(reference, f, indent=2, sort_keys=True)

        self._sp500_reference = reference
        return reference

    @staticmethod
    def _growth_profile_from_sector(sector: str) -> str:
        high = {"Technology", "Communication Services", "Consumer Discretionary"}
        low = {"Utilities", "Consumer Staples", "Real Estate"}
        if sector in high:
            return "high"
        if sector in low:
            return "low"
        return "medium"

    def _build_record_from_reference(self, ticker: str, ref: Dict[str, Any], source: str) -> Dict[str, Any]:
        sector = ref.get("sector") or "Unknown"
        return {
            "name": ref.get("name") or ticker,
            "sector": sector,
            "industry": ref.get("industry") or "Unknown",
            "country": ref.get("country") or "Unknown",
            "market_cap": None,
            "beta": None,
            "risk_profile": "medium",
            "growth_profile": self._growth_profile_from_sector(sector),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
        }

    def run(
        self,
        tickers: List[str],
        overwrite: bool = False,
        force_refresh: bool = False,
    ) -> PipelineResult:
        cleaned_tickers = []
        for ticker in tickers:
            normalized = ticker.strip().upper()
            if normalized:
                cleaned_tickers.append(normalized)

        existing_data = {} if overwrite else self._load_existing()
        info_cache = self._load_cache()
        saved: Dict[str, Dict[str, Any]] = {}
        failed: Dict[str, str] = {}
        total = len(cleaned_tickers)

        for index, ticker in enumerate(cleaned_tickers, start=1):
            self._log(f"Processing {index}/{total}: {ticker}")
            try:
                if ticker in existing_data and not force_refresh:
                    self._log(f"[{ticker}] already present, skipping (use --force-refresh to update)")
                    continue

                info = info_cache.get(ticker)
                if self._yahoo_rate_limited:
                    self._log(f"[{ticker}] yahoo in rate-limited mode, using fallback directly")
                    info = None

                if info is None or force_refresh:
                    try:
                        if self._yahoo_rate_limited:
                            raise RuntimeError("Yahoo rate limited; switching to fallback mode")
                        info = self._fetch_info_with_retry(ticker)
                        info_cache[ticker] = self._to_jsonable(info)
                        self._save_cache(info_cache)
                        saved[ticker] = self._build_record(ticker, info)
                        self._log(f"[{ticker}] waiting {self.delay_seconds:.1f}s for rate-limit safety")
                        time.sleep(self.delay_seconds)
                    except Exception as fetch_exc:
                        self._log(f"[{ticker}] primary source failed: {fetch_exc}")
                        sp500_ref = self._load_sp500_reference()
                        fallback = sp500_ref.get(self._normalize_symbol(ticker))
                        if not fallback:
                            fallback = DEFAULT_FALLBACK_REFERENCE.get(self._normalize_symbol(ticker))
                            if fallback:
                                self._log(f"[{ticker}] using built-in fallback reference")
                        if not fallback:
                            raise RuntimeError(
                                "Primary source failed and fallback reference has no match"
                            ) from fetch_exc
                        saved[ticker] = self._build_record_from_reference(
                            ticker,
                            fallback,
                            source="wikipedia_sp500_fallback",
                        )
                        self._log(f"[{ticker}] fallback source used successfully")
                else:
                    self._log(f"[{ticker}] using local cache")
                    saved[ticker] = self._build_record(ticker, info)
                existing_data[ticker] = saved[ticker]
                self._save_output(existing_data)
                self._log(f"[{ticker}] saved to output")
            except Exception as exc:
                failed[ticker] = str(exc)
                self._log(f"[{ticker}] failed: {exc}")

        final_data = dict(existing_data)
        final_data.update(saved)

        self._save_output(final_data)

        return PipelineResult(saved=saved, failed=failed)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch company metadata and store it in company_metadata.json"
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        required=False,
        help="List of ticker symbols to fetch (example: AAPL MSFT TSLA)",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Path to output JSON file",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite file instead of merging with existing records",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Refresh ticker data even if it is already in output JSON",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=1.0,
        help="Delay between successful external requests",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=4,
        help="Maximum retry attempts per ticker when requests fail",
    )
    parser.add_argument(
        "--use-seed-list",
        action="store_true",
        help="Use a built-in starter ticker list for initial data transfer",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Disable live progress logs",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    output_path = Path(args.output).resolve()

    tickers = args.tickers or []
    if args.use_seed_list:
        tickers = list(dict.fromkeys(tickers + DEFAULT_SEED_TICKERS))
    if not tickers:
        raise SystemExit("No tickers provided. Use --tickers or --use-seed-list.")

    pipeline = CompanyMetadataPipeline(
        output_path=output_path,
        delay_seconds=max(0.0, args.delay_seconds),
        max_retries=max(1, args.max_retries),
        verbose=not args.quiet,
    )
    result = pipeline.run(
        tickers=tickers,
        overwrite=args.overwrite,
        force_refresh=args.force_refresh,
    )

    print(f"Saved {len(result.saved)} ticker(s) to {output_path}")
    if result.saved:
        print("Success:", ", ".join(sorted(result.saved.keys())))
    if result.failed:
        print(f"Failed {len(result.failed)} ticker(s):")
        for ticker, message in sorted(result.failed.items()):
            print(f"  - {ticker}: {message}")


if __name__ == "__main__":
    main()
