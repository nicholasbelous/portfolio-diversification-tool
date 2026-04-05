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


@dataclass
class FinancialFetchResult:
    saved: Dict[str, Dict[str, Any]]
    failed: Dict[str, str]
    skipped: List[str]


class FinancialDataService:
    """
    Fetches and persists financial snapshots for tickers.
    Uses Yahoo Finance as primary source with retry/backoff and local caching.
    Falls back to price-history-only metrics if fundamentals are rate-limited.
    """

    def __init__(
        self,
        output_path: Optional[Path] = None,
        info_cache_path: Optional[Path] = None,
        sec_ticker_map_cache_path: Optional[Path] = None,
        sec_facts_cache_dir: Optional[Path] = None,
        schema_path: Optional[Path] = None,
        delay_seconds: float = 1.0,
        max_retries: int = 4,
        verbose: bool = True,
    ):
        data_root = Path(__file__).resolve().parent.parent / "data"
        self.output_path = output_path or data_root / "static" / "company_financials.json"
        self.info_cache_path = info_cache_path or data_root / "cache" / "financial_info_cache.json"
        self.sec_ticker_map_cache_path = sec_ticker_map_cache_path or data_root / "cache" / "sec_ticker_map.json"
        self.sec_facts_cache_dir = sec_facts_cache_dir or data_root / "cache" / "sec_companyfacts"
        self.schema_path = schema_path or data_root / "static" / "financial_fields_schema.json"
        self.delay_seconds = delay_seconds
        self.max_retries = max_retries
        self.verbose = verbose
        self._yahoo_rate_limited = False
        self._sec_user_agent = os.getenv(
            "SEC_USER_AGENT",
            "PortfolioDiversificationTool/1.0 (contact@example.com)",
        )

    def _log(self, message: str) -> None:
        if self.verbose:
            print(message, flush=True)

    @staticmethod
    def _to_jsonable(value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, dict):
            return {str(k): FinancialDataService._to_jsonable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [FinancialDataService._to_jsonable(v) for v in value]
        return str(value)

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

    def get_required_fields_schema(self) -> Dict[str, Any]:
        return self._load_json_dict(self.schema_path)

    def _fetch_info_with_retry(self, ticker: str) -> Dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            attempt_num = attempt + 1
            try:
                self._log(f"[{ticker}] fundamentals attempt {attempt_num}/{self.max_retries}")
                info = yf.Ticker(ticker).info
                if not info or info.get("quoteType") is None:
                    raise ValueError("No fundamentals returned")
                return info
            except Exception as exc:
                last_exc = exc
                if "Too Many Requests" in str(exc):
                    self._yahoo_rate_limited = True
                    raise RuntimeError("Yahoo fundamentals rate-limited") from exc
                wait_seconds = self.delay_seconds * (2**attempt)
                self._log(f"[{ticker}] fundamentals failed: {exc}. retrying in {wait_seconds:.1f}s")
                time.sleep(wait_seconds)
        raise RuntimeError(f"Fundamentals fetch failed after retries: {last_exc}")

    def _fetch_yahoo_chart_history(self, ticker: str, range_value: str = "1y", interval: str = "1d") -> pd.DataFrame:
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            f"?range={range_value}&interval={interval}"
        )
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        response = requests.get(url, headers=headers, timeout=30)
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
        highs = quote.get("high") or []
        lows = quote.get("low") or []
        volumes = quote.get("volume") or []

        if not timestamps or not closes:
            raise ValueError("Chart API returned empty series")

        frame = pd.DataFrame(
            {
                "Close": closes,
                "High": highs if len(highs) == len(timestamps) else [None] * len(timestamps),
                "Low": lows if len(lows) == len(timestamps) else [None] * len(timestamps),
                "Volume": volumes if len(volumes) == len(timestamps) else [None] * len(timestamps),
            },
            index=pd.to_datetime(timestamps, unit="s", utc=True),
        )

        frame = frame.dropna(subset=["Close"])
        if frame.empty:
            raise ValueError("Chart API close series empty after cleanup")

        return frame

    def _fetch_history_with_retry(self, ticker: str, period: str = "1y", interval: str = "1d") -> tuple[pd.DataFrame, str]:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            attempt_num = attempt + 1
            try:
                self._log(f"[{ticker}] prices(chart) attempt {attempt_num}/{self.max_retries}")
                chart_df = self._fetch_yahoo_chart_history(ticker=ticker, range_value=period, interval=interval)
                return chart_df, "yahoo_chart_api"
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

    def _sec_get_with_retry(self, url: str) -> Dict[str, Any]:
        last_exc: Exception | None = None
        headers = {"User-Agent": self._sec_user_agent, "Accept": "application/json"}
        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                return response.json()
            except Exception as exc:
                last_exc = exc
                wait_seconds = self.delay_seconds * (2**attempt)
                time.sleep(wait_seconds)
        raise RuntimeError(f"SEC request failed after retries: {last_exc}")

    def _load_sec_ticker_map(self) -> Dict[str, str]:
        cached = self._load_json_dict(self.sec_ticker_map_cache_path)
        if cached:
            return {k.upper(): str(v) for k, v in cached.items()}

        url = "https://www.sec.gov/files/company_tickers.json"
        raw = self._sec_get_with_retry(url)
        mapping: Dict[str, str] = {}
        for entry in raw.values():
            ticker = str(entry.get("ticker", "")).upper().strip()
            cik_num = entry.get("cik_str")
            if ticker and cik_num:
                mapping[ticker] = str(cik_num).zfill(10)
        self._save_json_dict(self.sec_ticker_map_cache_path, mapping)
        return mapping

    def _sec_companyfacts_cache_file(self, ticker: str) -> Path:
        return self.sec_facts_cache_dir / f"{ticker.upper()}.json"

    def _load_sec_companyfacts(self, ticker: str) -> Optional[Dict[str, Any]]:
        cache_file = self._sec_companyfacts_cache_file(ticker)
        cached = self._load_json_dict(cache_file)
        if cached:
            return cached

        ticker_map = self._load_sec_ticker_map()
        cik = ticker_map.get(ticker.upper())
        if not cik:
            return None

        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        data = self._sec_get_with_retry(url)
        self._save_json_dict(cache_file, data)
        return data

    @staticmethod
    def _extract_latest_fact(companyfacts: Dict[str, Any], tag: str, unit_candidates: List[str]) -> Optional[float]:
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
        companyfacts = self._load_sec_companyfacts(ticker)
        if not companyfacts:
            return None

        revenue = self._extract_latest_fact(
            companyfacts,
            "Revenues",
            ["USD"],
        ) or self._extract_latest_fact(
            companyfacts,
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            ["USD"],
        ) or self._extract_latest_fact(
            companyfacts,
            "SalesRevenueNet",
            ["USD"],
        )
        net_income = self._extract_latest_fact(companyfacts, "NetIncomeLoss", ["USD"])
        operating_income = self._extract_latest_fact(companyfacts, "OperatingIncomeLoss", ["USD"])
        assets = self._extract_latest_fact(companyfacts, "Assets", ["USD"])
        equity = self._extract_latest_fact(companyfacts, "StockholdersEquity", ["USD"])
        liabilities = self._extract_latest_fact(companyfacts, "Liabilities", ["USD"])
        cash = self._extract_latest_fact(companyfacts, "CashAndCashEquivalentsAtCarryingValue", ["USD"])
        operating_cf = self._extract_latest_fact(
            companyfacts,
            "NetCashProvidedByUsedInOperatingActivities",
            ["USD"],
        )
        capex = self._extract_latest_fact(
            companyfacts,
            "PaymentsToAcquirePropertyPlantAndEquipment",
            ["USD"],
        )
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

        enterprise_value = None
        if market_cap is not None and liabilities is not None:
            enterprise_value = market_cap + liabilities - (cash or 0.0)

        free_cash_flow = None
        if operating_cf is not None:
            if capex is not None:
                free_cash_flow = operating_cf - abs(capex)
            else:
                free_cash_flow = operating_cf

        return {
            "shortName": companyfacts.get("entityName") or ticker,
            "longName": companyfacts.get("entityName") or ticker,
            "marketCap": market_cap,
            "enterpriseValue": enterprise_value,
            "trailingPE": trailing_pe,
            "forwardPE": None,
            "priceToBook": price_to_book,
            "trailingEps": eps_ttm,
            "dividendYield": None,
            "beta": None,
            "revenueGrowth": None,
            "earningsGrowth": None,
            "debtToEquity": self._safe_ratio(liabilities, equity),
            "profitMargins": self._safe_ratio(net_income, revenue),
            "operatingMargins": self._safe_ratio(operating_income, revenue),
            "returnOnEquity": self._safe_ratio(net_income, equity),
            "returnOnAssets": self._safe_ratio(net_income, assets),
            "freeCashflow": free_cash_flow,
            "totalRevenue": revenue,
        }

    def _price_return(self, close: pd.Series, lookback_days: int) -> Optional[float]:
        if close.empty:
            return None
        if len(close) <= lookback_days:
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
                "return_6m": None,
                "return_1y": None,
                "volatility_1y": None,
                "high_52w": None,
                "low_52w": None,
            }

        daily_returns = close.pct_change().dropna()
        volatility = None
        if not daily_returns.empty:
            volatility = float(daily_returns.std() * (252**0.5))

        return {
            "latest_close": float(close.iloc[-1]),
            "return_1m": self._price_return(close, 21),
            "return_3m": self._price_return(close, 63),
            "return_6m": self._price_return(close, 126),
            "return_1y": self._price_return(close, 252),
            "volatility_1y": volatility,
            "high_52w": float(close.max()),
            "low_52w": float(close.min()),
        }

    @staticmethod
    def _empty_price_metrics() -> Dict[str, Optional[float]]:
        return {
            "latest_close": None,
            "return_1m": None,
            "return_3m": None,
            "return_6m": None,
            "return_1y": None,
            "volatility_1y": None,
            "high_52w": None,
            "low_52w": None,
        }

    def _build_snapshot(
        self,
        ticker: str,
        info: Optional[Dict[str, Any]],
        price_metrics: Dict[str, Optional[float]],
        fundamentals_source: str,
        price_source: str,
    ) -> Dict[str, Any]:
        info = info or {}
        snapshot = {
            "ticker": ticker,
            "name": info.get("shortName") or info.get("longName") or ticker,
            "fundamentals": {
                "market_cap": self._to_float(info.get("marketCap")),
                "enterprise_value": self._to_float(info.get("enterpriseValue")),
                "trailing_pe": self._to_float(info.get("trailingPE")),
                "forward_pe": self._to_float(info.get("forwardPE")),
                "price_to_book": self._to_float(info.get("priceToBook")),
                "eps_ttm": self._to_float(info.get("trailingEps")),
                "dividend_yield": self._to_float(info.get("dividendYield")),
                "beta": self._to_float(info.get("beta")),
                "revenue_growth": self._to_float(info.get("revenueGrowth")),
                "earnings_growth": self._to_float(info.get("earningsGrowth")),
                "debt_to_equity": self._to_float(info.get("debtToEquity")),
                "profit_margin": self._to_float(info.get("profitMargins")),
                "operating_margin": self._to_float(info.get("operatingMargins")),
                "return_on_equity": self._to_float(info.get("returnOnEquity")),
                "return_on_assets": self._to_float(info.get("returnOnAssets")),
                "free_cash_flow": self._to_float(info.get("freeCashflow")),
                "total_revenue": self._to_float(info.get("totalRevenue")),
            },
            "price_metrics": price_metrics,
            "sources": {
                "fundamentals": fundamentals_source,
                "price_metrics": price_source,
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        return snapshot

    def fetch_and_store(
        self,
        tickers: List[str],
        force_refresh: bool = False,
    ) -> FinancialFetchResult:
        cleaned_tickers = []
        for ticker in tickers:
            normalized = ticker.strip().upper()
            if normalized:
                cleaned_tickers.append(normalized)

        saved: Dict[str, Dict[str, Any]] = {}
        failed: Dict[str, str] = {}
        skipped: List[str] = []

        stored = self._load_json_dict(self.output_path)
        info_cache = self._load_json_dict(self.info_cache_path)

        total = len(cleaned_tickers)
        for index, ticker in enumerate(cleaned_tickers, start=1):
            self._log(f"Processing {index}/{total}: {ticker}")

            if ticker in stored and not force_refresh:
                skipped.append(ticker)
                self._log(f"[{ticker}] already present, skipping")
                continue

            info: Optional[Dict[str, Any]] = None
            fundamentals_source = "none"
            try:
                history, price_source = self._fetch_history_with_retry(ticker)
                price_metrics = self._build_price_metrics(history)
            except Exception as exc:
                self._log(f"[{ticker}] price metrics unavailable: {exc}")
                price_metrics = self._empty_price_metrics()
                price_source = "unavailable"

            latest_close = self._to_float(price_metrics.get("latest_close"))

            try:
                if self._yahoo_rate_limited:
                    raise RuntimeError("Yahoo fundamentals rate-limited")

                cached_info = info_cache.get(ticker)
                if cached_info and not force_refresh:
                    info = cached_info
                    fundamentals_source = "yfinance_cache"
                    self._log(f"[{ticker}] using cached fundamentals")
                else:
                    info = self._fetch_info_with_retry(ticker)
                    info_cache[ticker] = self._to_jsonable(info)
                    self._save_json_dict(self.info_cache_path, info_cache)
                    fundamentals_source = "yfinance"
                    self._log(f"[{ticker}] fundamentals saved to cache")
                    time.sleep(self.delay_seconds)
            except Exception as exc:
                self._log(f"[{ticker}] yfinance fundamentals unavailable: {exc}")
                try:
                    sec_info = self._build_fundamentals_from_sec(ticker=ticker, latest_close=latest_close)
                    if sec_info:
                        info = sec_info
                        fundamentals_source = "sec_companyfacts"
                        self._log(f"[{ticker}] SEC fundamentals fallback used")
                except Exception as sec_exc:
                    self._log(f"[{ticker}] SEC fundamentals unavailable: {sec_exc}")

            snapshot = self._build_snapshot(
                ticker=ticker,
                info=info,
                price_metrics=price_metrics,
                fundamentals_source=fundamentals_source,
                price_source=price_source,
            )

            stored[ticker] = snapshot
            self._save_json_dict(self.output_path, stored)
            saved[ticker] = snapshot
            if fundamentals_source == "none" and price_source == "unavailable":
                failed[ticker] = "No fundamentals or price metrics available from current providers"
                self._log(f"[{ticker}] saved placeholder snapshot (data unavailable)")
            else:
                self._log(f"[{ticker}] saved financial snapshot")

        return FinancialFetchResult(saved=saved, failed=failed, skipped=skipped)
