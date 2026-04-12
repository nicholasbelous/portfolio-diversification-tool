CREATE TABLE IF NOT EXISTS price_history_daily (
    ticker TEXT NOT NULL,
    trading_date DATE NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    source_prices TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (ticker, trading_date),
    FOREIGN KEY (ticker) REFERENCES companies(ticker) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_price_history_ticker_date
    ON price_history_daily(ticker, trading_date DESC);
