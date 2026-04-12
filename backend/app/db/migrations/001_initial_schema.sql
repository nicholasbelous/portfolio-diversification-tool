CREATE TABLE IF NOT EXISTS companies (
    ticker TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sector TEXT,
    industry TEXT,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS financial_snapshots (
    ticker TEXT PRIMARY KEY,
    market_cap DOUBLE PRECISION,
    beta DOUBLE PRECISION,
    trailing_pe DOUBLE PRECISION,
    price_to_book DOUBLE PRECISION,
    debt_to_equity DOUBLE PRECISION,
    profit_margin DOUBLE PRECISION,
    latest_close DOUBLE PRECISION,
    return_1m DOUBLE PRECISION,
    return_3m DOUBLE PRECISION,
    return_1y DOUBLE PRECISION,
    volatility_1y DOUBLE PRECISION,
    source_fundamentals TEXT NOT NULL,
    source_prices TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    FOREIGN KEY (ticker) REFERENCES companies(ticker) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_companies_sector ON companies(sector);
