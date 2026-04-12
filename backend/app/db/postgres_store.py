from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

import psycopg2
from psycopg2.extras import RealDictCursor, execute_batch


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

    def fetch_snapshot_by_ticker(self, ticker: str) -> Optional[Dict[str, Any]]:
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
                    WHERE c.ticker = %s
                    """,
                    (ticker.upper(),),
                )
                return cur.fetchone()

    def fetch_top_snapshots(self, metric: str, limit: int = 25) -> List[Dict[str, Any]]:
        metric_map = {
            "beta": "beta",
            "volatility_1y": "volatility_1y",
            "return_1y": "return_1y",
            "return_3m": "return_3m",
            "return_1m": "return_1m",
        }
        metric_column = metric_map.get(metric)
        if metric_column is None:
            raise ValueError(f"Unsupported metric: {metric}")

        safe_limit = max(1, min(int(limit), 500))
        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    f"""
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
                    WHERE f.{metric_column} IS NOT NULL
                    ORDER BY f.{metric_column} DESC NULLS LAST
                    LIMIT %s
                    """,
                    (safe_limit,),
                )
                return list(cur.fetchall())

    def upsert_price_history(self, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        payload = [
            (
                row["ticker"],
                row["trading_date"],
                row["close"],
                row["source_prices"],
                row["updated_at"],
            )
            for row in rows
        ]
        with self._connect() as conn:
            with conn.cursor() as cur:
                execute_batch(
                    cur,
                    """
                    INSERT INTO price_history_daily (
                        ticker, trading_date, close, source_prices, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (ticker, trading_date) DO UPDATE SET
                        close = excluded.close,
                        source_prices = excluded.source_prices,
                        updated_at = excluded.updated_at
                    """,
                    payload,
                    page_size=1000,
                )
            conn.commit()

    def fetch_price_history(
        self,
        ticker: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 5000))
        sql = """
            SELECT ticker, trading_date, close, source_prices, updated_at
            FROM price_history_daily
            WHERE ticker = %s
        """
        params: List[Any] = [ticker.upper()]
        if start_date is not None:
            sql += " AND trading_date >= %s"
            params.append(start_date)
        if end_date is not None:
            sql += " AND trading_date <= %s"
            params.append(end_date)
        sql += " ORDER BY trading_date ASC LIMIT %s"
        params.append(safe_limit)

        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, tuple(params))
                return list(cur.fetchall())

    def fetch_snapshot_tickers(self) -> Set[str]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT ticker FROM financial_snapshots")
                return {row[0] for row in cur.fetchall()}

    def count_financial_snapshots(self) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM financial_snapshots")
                row = cur.fetchone()
                return int(row[0]) if row else 0

    def count_price_history_rows(self) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM price_history_daily")
                row = cur.fetchone()
                return int(row[0]) if row else 0
