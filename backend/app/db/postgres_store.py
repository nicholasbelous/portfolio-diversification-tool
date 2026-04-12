from pathlib import Path
from typing import Any, Dict, Iterable

import psycopg2
from psycopg2.extras import RealDictCursor


class PostgresStore:
    """
    Minimal Postgres store with SQL-file migrations and upsert helpers.
    """

    def __init__(self, database_url: str, migrations_dir: Path):
        self.database_url = database_url
        self.migrations_dir = migrations_dir
        self.migrate()

    def _connect(self):
        return psycopg2.connect(self.database_url)

    def migrate(self) -> None:
        self.migrations_dir.mkdir(parents=True, exist_ok=True)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version TEXT PRIMARY KEY,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cur.execute("SELECT version FROM schema_migrations")
                applied = {row[0] for row in cur.fetchall()}

                migration_files = sorted(self.migrations_dir.glob("*.sql"))
                for migration_file in migration_files:
                    version = migration_file.name.split("_", maxsplit=1)[0]
                    if version in applied:
                        continue

                    sql_script = migration_file.read_text(encoding="utf-8")
                    cur.execute(sql_script)
                    cur.execute(
                        "INSERT INTO schema_migrations(version) VALUES (%s)",
                        (version,),
                    )
            conn.commit()

    def upsert_company(self, company: Dict[str, object]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO companies (ticker, name, sector, industry, updated_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT(ticker) DO UPDATE SET
                        name = excluded.name,
                        sector = excluded.sector,
                        industry = excluded.industry,
                        updated_at = excluded.updated_at
                    """,
                    (
                        company["ticker"],
                        company["name"],
                        company["sector"],
                        company["industry"],
                        company["updated_at"],
                    ),
                )
            conn.commit()

    def upsert_financial_snapshot(self, snapshot: Dict[str, object]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO financial_snapshots (
                        ticker,
                        market_cap,
                        beta,
                        trailing_pe,
                        price_to_book,
                        debt_to_equity,
                        profit_margin,
                        latest_close,
                        return_1m,
                        return_3m,
                        return_1y,
                        volatility_1y,
                        source_fundamentals,
                        source_prices,
                        updated_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s
                    )
                    ON CONFLICT(ticker) DO UPDATE SET
                        market_cap = excluded.market_cap,
                        beta = excluded.beta,
                        trailing_pe = excluded.trailing_pe,
                        price_to_book = excluded.price_to_book,
                        debt_to_equity = excluded.debt_to_equity,
                        profit_margin = excluded.profit_margin,
                        latest_close = excluded.latest_close,
                        return_1m = excluded.return_1m,
                        return_3m = excluded.return_3m,
                        return_1y = excluded.return_1y,
                        volatility_1y = excluded.volatility_1y,
                        source_fundamentals = excluded.source_fundamentals,
                        source_prices = excluded.source_prices,
                        updated_at = excluded.updated_at
                    """,
                    (
                        snapshot["ticker"],
                        snapshot["market_cap"],
                        snapshot["beta"],
                        snapshot["trailing_pe"],
                        snapshot["price_to_book"],
                        snapshot["debt_to_equity"],
                        snapshot["profit_margin"],
                        snapshot["latest_close"],
                        snapshot["return_1m"],
                        snapshot["return_3m"],
                        snapshot["return_1y"],
                        snapshot["volatility_1y"],
                        snapshot["source_fundamentals"],
                        snapshot["source_prices"],
                        snapshot["updated_at"],
                    ),
                )
            conn.commit()

    def fetch_all_snapshots(self) -> Iterable[Dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        c.ticker,
                        c.name,
                        c.sector,
                        c.industry,
                        f.market_cap,
                        f.beta,
                        f.trailing_pe,
                        f.price_to_book,
                        f.debt_to_equity,
                        f.profit_margin,
                        f.latest_close,
                        f.return_1m,
                        f.return_3m,
                        f.return_1y,
                        f.volatility_1y,
                        f.source_fundamentals,
                        f.source_prices,
                        f.updated_at
                    FROM financial_snapshots f
                    JOIN companies c ON c.ticker = f.ticker
                    ORDER BY c.ticker
                    """
                )
                return cur.fetchall()
