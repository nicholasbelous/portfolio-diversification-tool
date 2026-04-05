import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
import yfinance as yf

try:
    from app.db import SQLiteStore
except ModuleNotFoundError:  # pragma: no cover - allows running from repo root
    from backend.app.db import SQLiteStore


@dataclass
class FinancialFetchResult:
    saved: Dict[str, Dict[str, Any]]
    failed: Dict[str, str]
    skipped: List[str]


class FinancialDataService:
    """
    Lean financial data service.
    Pulls only required fields and persists them to SQLite + lightweight JSON.
    """

    def __init__(
        self,
        output_path: Optional[Path] = None,
        db_path: Optional[Path] = None,
        sec_ticker_map_cache_path: Optional[Path] = None,
        metadata_path: Optional[Path] = None,
        sp500_reference_path: Optional[Path] = None,
        schema_path: Optional[Path] = None,
        delay_seconds: float = 1.0,
        per_ticker_delay_seconds: float = 0.0,
        max_retries: int = 4,
        verbose: bool = True,
    ):
        data_root = Path(__file__).resolve().parent.parent / "data"
        self.output_path = output_path or data_root / "static" / "company_financials.json"
        self.db_path = db_path or data_root / "static" / "portfolio_data.db"
        self.schema_path = schema_path or data_root / "static" / "financial_fields_schema.json"
        self.metadata_path = metadata_path or data_root / "static" / "company_metadata.json"
        self.sp500_reference_path = sp500_reference_path or data_root / "cache" / "sp500_reference.json"
        self.sec_ticker_map_cache_path = (
            sec_ticker_map_cache_path or data_root / "cache" / "sec_ticker_map.json"
        )
        self.delay_seconds = delay_seconds
        self.per_ticker_delay_seconds = per_ticker_delay_seconds
        self.max_retries = max_retries
        self.verbose = verbose
        self._yahoo_rate_limited = False
        self._sec_ticker_map: Optional[Dict[str, str]] = None
        self._sec_user_agent = os.getenv(
            "SEC_USER_AGENT",
            "PortfolioDiversificationTool/1.0 (contact@example.com)",
        )
        self._http = requests.Session()
        self._http.headers.update({"User-Agent": "Mozilla/5.0"})
        self._metadata_context = self._load_metadata_context()

        migrations_dir = Path(__file__).resolve().parent.parent / "db" / "migrations"
        self.store = SQLiteStore(db_path=self.db_path, migrations_dir=migrations_dir)

    def _log(self, message: str) -> None:
        if self.verbose:
            print(message, flush=True)

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
        if numerator is None or denominator in (None, 0):
            return None
        return numerator / denominator

    def _load_json_dict(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        return {}

    def _save_json_dict(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)

    def _load_metadata_context(self) -> Dict[str, Dict[str, str]]:
        payload = self._load_json_dict(self.metadata_path)
        context: Dict[str, Dict[str, str]] = {}
        for ticker, row in payload.items():
            if not isinstance(row, dict):
                continue
            symbol = str(ticker).upper()
            context[symbol] = {
                "name": str(row.get("name") or symbol),
                "sector": str(row.get("sector") or "Unknown"),
                "industry": str(row.get("industry") or "Unknown"),
            }

        sp500_payload = self._load_json_dict(self.sp500_reference_path)
        for ticker, row in sp500_payload.items():
            if not isinstance(row, dict):
                continue
            symbol = str(ticker).upper().replace(".", "-")
            if symbol not in context:
                context[symbol] = {
                    "name": str(row.get("name") or symbol),
                    "sector": str(row.get("sector") or "Unknown"),
                    "industry": str(row.get("industry") or "Unknown"),
                }
        return context

    def get_required_fields_schema(self) -> Dict[str, Any]:
        return self._load_json_dict(self.schema_path)

    def _fetch_yahoo_chart_history(
        self,
        ticker: str,
        range_value: str = "1y",
        interval: str = "1d",
    ) -> pd.DataFrame:
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            f"?range={range_value}&interval={interval}"
        )
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        response = self._http.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        payload = response.json()

        chart = payload.get("chart", {})
        if chart.get("error"):
            raise ValueError(f"Chart API error: {chart['error']}")

        result = (chart.get("result") or [None])[0]
        if not result:
            raise ValueError("No chart result returned")

        timestamps = result.get("timestamp") or []
        quote = ((result.get("indicators") or {}).get("quote") or [None])[0] or {}
        closes = quote.get("close") or []

        if not timestamps or not closes:
            raise ValueError("Chart API returned empty series")

        df = pd.DataFrame(
            {"Close": closes},
            index=pd.to_datetime(timestamps, unit="s", utc=True),
        )
        df = df.dropna(subset=["Close"])
        if df.empty:
            raise ValueError("Chart API close series empty after cleanup")
        return df

    def _fetch_history_with_retry(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> tuple[pd.DataFrame, str]:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            attempt_num = attempt + 1
            try:
                self._log(f"[{ticker}] prices(chart) attempt {attempt_num}/{self.max_retries}")
                return (
                    self._fetch_yahoo_chart_history(ticker=ticker, range_value=period, interval=interval),
                    "yahoo_chart_api",
                )
            except Exception as chart_exc:
                last_exc = chart_exc
                self._log(f"[{ticker}] chart api failed: {chart_exc}")

            try:
                self._log(f"[{ticker}] prices(yfinance) attempt {attempt_num}/{self.max_retries}")
                df = yf.download(
                    tickers=ticker,
                    period=period,
                    interval=interval,
                    progress=False,
                    auto_adjust=True,
                    threads=False,
                )
                if df.empty:
                    raise ValueError("No price history returned")
                return df, "yfinance_history"
            except Exception as exc:
                last_exc = exc
                wait_seconds = self.delay_seconds * (2**attempt)
                self._log(f"[{ticker}] prices failed: {exc}. retrying in {wait_seconds:.1f}s")
                time.sleep(wait_seconds)
        raise RuntimeError(f"Price history fetch failed after retries: {last_exc}")

    def _price_return(self, close: pd.Series, lookback_days: int) -> Optional[float]:
        if close.empty or len(close) <= lookback_days:
            return None
        latest = close.iloc[-1]
        prior = close.iloc[-(lookback_days + 1)]
        if prior == 0:
            return None
        return float((latest / prior) - 1.0)

    def _build_price_metrics(self, history: pd.DataFrame) -> Dict[str, Optional[float]]:
        close = history["Close"].dropna()
        if close.empty:
            return {
                "latest_close": None,
                "return_1m": None,
                "return_3m": None,
                "return_1y": None,
                "volatility_1y": None,
            }

        daily_returns = close.pct_change().dropna()
        volatility = None
        if not daily_returns.empty:
            volatility = float(daily_returns.std() * (252**0.5))

        return {
            "latest_close": float(close.iloc[-1]),
            "return_1m": self._price_return(close, 21),
            "return_3m": self._price_return(close, 63),
            "return_1y": self._price_return(close, 252),
            "volatility_1y": volatility,
        }

    def _sec_get_with_retry(self, url: str) -> Dict[str, Any]:
        last_exc: Exception | None = None
        headers = {"User-Agent": self._sec_user_agent, "Accept": "application/json"}
        for attempt in range(self.max_retries):
            try:
                response = self._http.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                return response.json()
            except Exception as exc:
                last_exc = exc
                wait_seconds = self.delay_seconds * (2**attempt)
                time.sleep(wait_seconds)
        raise RuntimeError(f"SEC request failed after retries: {last_exc}")

    def _load_sec_ticker_map(self) -> Dict[str, str]:
        if self._sec_ticker_map is not None:
            return self._sec_ticker_map

        cached = self._load_json_dict(self.sec_ticker_map_cache_path)
        if cached:
            self._sec_ticker_map = {k.upper(): str(v) for k, v in cached.items()}
            return self._sec_ticker_map

        url = "https://www.sec.gov/files/company_tickers.json"
        raw = self._sec_get_with_retry(url)
        mapping: Dict[str, str] = {}
        for entry in raw.values():
            ticker = str(entry.get("ticker", "")).upper().strip()
            cik_num = entry.get("cik_str")
            if ticker and cik_num:
                mapping[ticker] = str(cik_num).zfill(10)
        self._save_json_dict(self.sec_ticker_map_cache_path, mapping)
        self._sec_ticker_map = mapping
        return mapping

    @staticmethod
    def _extract_latest_fact(
        companyfacts: Dict[str, Any],
        tag: str,
        unit_candidates: List[str],
    ) -> Optional[float]:
        facts = companyfacts.get("facts", {})
        us_gaap = facts.get("us-gaap", {})
        dei = facts.get("dei", {})
        tag_block = us_gaap.get(tag) or dei.get(tag)
        if not tag_block:
            return None

        units = tag_block.get("units", {})
        for unit in unit_candidates:
            values = units.get(unit)
            if not values:
                continue
            sorted_values = sorted(
                values,
                key=lambda x: (
                    str(x.get("end", "")),
                    str(x.get("filed", "")),
                    str(x.get("fy", "")),
                ),
            )
            for item in reversed(sorted_values):
                try:
                    return float(item.get("val"))
                except (TypeError, ValueError):
                    continue
        return None

    def _build_fundamentals_from_sec(
        self,
        ticker: str,
        latest_close: Optional[float],
    ) -> Optional[Dict[str, Any]]:
        ticker_map = self._load_sec_ticker_map()
        cik = ticker_map.get(ticker.upper())
        if not cik:
            return None

        companyfacts = self._sec_get_with_retry(
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        )

        revenue = self._extract_latest_fact(companyfacts, "Revenues", ["USD"]) or self._extract_latest_fact(
            companyfacts,
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            ["USD"],
        ) or self._extract_latest_fact(companyfacts, "SalesRevenueNet", ["USD"])
        net_income = self._extract_latest_fact(companyfacts, "NetIncomeLoss", ["USD"])
        equity = self._extract_latest_fact(companyfacts, "StockholdersEquity", ["USD"])
        liabilities = self._extract_latest_fact(companyfacts, "Liabilities", ["USD"])
        shares_outstanding = self._extract_latest_fact(
            companyfacts,
            "CommonStockSharesOutstanding",
            ["shares"],
        ) or self._extract_latest_fact(
            companyfacts,
            "EntityCommonStockSharesOutstanding",
            ["shares"],
        )
        eps_ttm = self._extract_latest_fact(
            companyfacts,
            "EarningsPerShareDiluted",
            ["USD/shares"],
        ) or self._extract_latest_fact(
            companyfacts,
            "EarningsPerShareBasic",
            ["USD/shares"],
        )

        market_cap = None
        if latest_close is not None and shares_outstanding is not None:
            market_cap = latest_close * shares_outstanding

        trailing_pe = None
        if latest_close is not None and eps_ttm not in (None, 0):
            trailing_pe = latest_close / eps_ttm

        price_to_book = None
        if market_cap is not None and equity not in (None, 0):
            price_to_book = market_cap / equity

        return {
            "name": companyfacts.get("entityName") or ticker,
            "market_cap": market_cap,
            "beta": None,
            "trailing_pe": trailing_pe,
            "price_to_book": price_to_book,
            "debt_to_equity": self._safe_ratio(liabilities, equity),
            "profit_margin": self._safe_ratio(net_income, revenue),
        }

    def _build_fundamentals_from_yfinance(self, ticker: str) -> Optional[Dict[str, Any]]:
        if self._yahoo_rate_limited:
            return None

        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            attempt_num = attempt + 1
            try:
                self._log(f"[{ticker}] fundamentals(yfinance) attempt {attempt_num}/{self.max_retries}")
                info = yf.Ticker(ticker).info
                if not info or info.get("quoteType") is None:
                    raise ValueError("No fundamentals returned")
                return {
                    "name": info.get("shortName") or info.get("longName") or ticker,
                    "market_cap": self._to_float(info.get("marketCap")),
                    "beta": self._to_float(info.get("beta")),
                    "trailing_pe": self._to_float(info.get("trailingPE")),
                    "price_to_book": self._to_float(info.get("priceToBook")),
                    "debt_to_equity": self._to_float(info.get("debtToEquity")),
                    "profit_margin": self._to_float(info.get("profitMargins")),
                }
            except Exception as exc:
                last_exc = exc
                if "Too Many Requests" in str(exc):
                    self._yahoo_rate_limited = True
                    break
                wait_seconds = self.delay_seconds * (2**attempt)
                time.sleep(wait_seconds)
        self._log(f"[{ticker}] yfinance fundamentals unavailable: {last_exc}")
        return None

    def _build_snapshot(
        self,
        ticker: str,
        fundamentals: Dict[str, Any],
        price_metrics: Dict[str, Optional[float]],
        source_fundamentals: str,
        source_prices: str,
    ) -> Dict[str, Any]:
        context = self._metadata_context.get(ticker, {})
        name = fundamentals.get("name") or context.get("name") or ticker
        sector = context.get("sector", "Unknown")
        industry = context.get("industry", "Unknown")

        return {
            "ticker": ticker,
            "name": name,
            "sector": sector,
            "industry": industry,
            "market_cap": self._to_float(fundamentals.get("market_cap")),
            "beta": self._to_float(fundamentals.get("beta")),
            "trailing_pe": self._to_float(fundamentals.get("trailing_pe")),
            "price_to_book": self._to_float(fundamentals.get("price_to_book")),
            "debt_to_equity": self._to_float(fundamentals.get("debt_to_equity")),
            "profit_margin": self._to_float(fundamentals.get("profit_margin")),
            "latest_close": self._to_float(price_metrics.get("latest_close")),
            "return_1m": self._to_float(price_metrics.get("return_1m")),
            "return_3m": self._to_float(price_metrics.get("return_3m")),
            "return_1y": self._to_float(price_metrics.get("return_1y")),
            "volatility_1y": self._to_float(price_metrics.get("volatility_1y")),
            "source_fundamentals": source_fundamentals,
            "source_prices": source_prices,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _persist_snapshot(self, snapshot: Dict[str, Any]) -> None:
        company_row = {
            "ticker": snapshot["ticker"],
            "name": snapshot["name"],
            "sector": snapshot["sector"],
            "industry": snapshot["industry"],
            "updated_at": snapshot["updated_at"],
        }
        financial_row = {
            "ticker": snapshot["ticker"],
            "market_cap": snapshot["market_cap"],
            "beta": snapshot["beta"],
            "trailing_pe": snapshot["trailing_pe"],
            "price_to_book": snapshot["price_to_book"],
            "debt_to_equity": snapshot["debt_to_equity"],
            "profit_margin": snapshot["profit_margin"],
            "latest_close": snapshot["latest_close"],
            "return_1m": snapshot["return_1m"],
            "return_3m": snapshot["return_3m"],
            "return_1y": snapshot["return_1y"],
            "volatility_1y": snapshot["volatility_1y"],
            "source_fundamentals": snapshot["source_fundamentals"],
            "source_prices": snapshot["source_prices"],
            "updated_at": snapshot["updated_at"],
        }

        self.store.upsert_company(company_row)
        self.store.upsert_financial_snapshot(financial_row)

    def fetch_and_store(
        self,
        tickers: List[str],
        force_refresh: bool = False,
    ) -> FinancialFetchResult:
        cleaned_tickers: List[str] = []
        for ticker in tickers:
            symbol = ticker.strip().upper()
            if symbol and symbol not in cleaned_tickers:
                cleaned_tickers.append(symbol)

        saved: Dict[str, Dict[str, Any]] = {}
        failed: Dict[str, str] = {}
        skipped: List[str] = []

        json_store = self._load_json_dict(self.output_path)

        total = len(cleaned_tickers)
        for index, ticker in enumerate(cleaned_tickers, start=1):
            self._log(f"Processing {index}/{total}: {ticker}")

            if ticker in json_store and not force_refresh:
                skipped.append(ticker)
                self._log(f"[{ticker}] already present, skipping")
                continue

            try:
                history, source_prices = self._fetch_history_with_retry(ticker)
                price_metrics = self._build_price_metrics(history)
            except Exception as exc:
                failed[ticker] = f"Unable to fetch prices: {exc}"
                self._log(f"[{ticker}] failed: {failed[ticker]}")
                continue

            fundamentals = self._build_fundamentals_from_yfinance(ticker)
            source_fundamentals = "yfinance"
            if fundamentals is None:
                try:
                    fundamentals = self._build_fundamentals_from_sec(
                        ticker=ticker,
                        latest_close=price_metrics.get("latest_close"),
                    )
                    source_fundamentals = "sec_companyfacts"
                except Exception as exc:
                    fundamentals = None
                    self._log(f"[{ticker}] SEC fallback unavailable: {exc}")

            if fundamentals is None:
                fundamentals = {"name": ticker}
                source_fundamentals = "unavailable"

            snapshot = self._build_snapshot(
                ticker=ticker,
                fundamentals=fundamentals,
                price_metrics=price_metrics,
                source_fundamentals=source_fundamentals,
                source_prices=source_prices,
            )

            self._persist_snapshot(snapshot)
            json_store[ticker] = snapshot
            self._save_json_dict(self.output_path, json_store)
            saved[ticker] = snapshot
            self._log(f"[{ticker}] saved lean snapshot")
            if self.per_ticker_delay_seconds > 0:
                time.sleep(self.per_ticker_delay_seconds)

        return FinancialFetchResult(saved=saved, failed=failed, skipped=skipped)
