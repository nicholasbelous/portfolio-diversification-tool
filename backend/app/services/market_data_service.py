import pandas as pd
import requests
import yfinance as yf


class MarketDataService:
    """
    Fetches historical market data using a single Yahoo Finance request.
    """

    @staticmethod
    def _fetch_yahoo_chart_history(
        ticker: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> pd.DataFrame:
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            f"?range={period}&interval={interval}"
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
        opens = quote.get("open") or []
        volumes = quote.get("volume") or []

        if not timestamps or not closes:
            raise ValueError("Chart API returned empty price series")

        df = pd.DataFrame(
            {
                "Open": opens if len(opens) == len(timestamps) else [None] * len(timestamps),
                "High": highs if len(highs) == len(timestamps) else [None] * len(timestamps),
                "Low": lows if len(lows) == len(timestamps) else [None] * len(timestamps),
                "Close": closes,
                "Volume": volumes if len(volumes) == len(timestamps) else [None] * len(timestamps),
            },
            index=pd.to_datetime(timestamps, unit="s", utc=True),
        )
        df = df.dropna(subset=["Close"])
        if df.empty:
            raise ValueError("Chart API close series empty after cleanup")
        return df

    def get_price_history(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> pd.DataFrame:
        ticker = ticker.upper()

        try:
            df = self._fetch_yahoo_chart_history(
                ticker=ticker,
                period=period,
                interval=interval,
            )
        except Exception:
            df = yf.download(
                tickers=ticker,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=True,
                threads=False,
            )

        if df.empty:
            raise ValueError(f"No price data returned for {ticker}")

        return df


# -------------------------
# Local test runner
# -------------------------
if __name__ == "__main__":
    service = MarketDataService()

    try:
        df = service.get_price_history("AAPL")
        print(df.tail())
    except Exception as e:
        print("ERROR:", e)
