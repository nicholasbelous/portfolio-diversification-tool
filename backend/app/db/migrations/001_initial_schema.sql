CREATE TABLE IF NOT EXISTS companies (
    ticker TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sector TEXT,
    industry TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS financial_snapshots (
    ticker TEXT PRIMARY KEY,
    market_cap REAL,
    beta REAL,
    trailing_pe REAL,
    price_to_book REAL,
    debt_to_equity REAL,
    profit_margin REAL,
    latest_close REAL,
    return_1m REAL,
    return_3m REAL,
    return_1y REAL,
    volatility_1y REAL,
    source_fundamentals TEXT NOT NULL,
    source_prices TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (ticker) REFERENCES companies(ticker) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_companies_sector ON companies(sector);
