import pandas as pd
import yfinance as yf


class MarketDataService:
    """
    Fetches historical market data using a single Yahoo Finance request.
    """

    def get_price_history(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> pd.DataFrame:
        ticker = ticker.upper()

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
