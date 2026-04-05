import sqlite3
from pathlib import Path
from typing import Dict, Iterable


class SQLiteStore:
    """
    Minimal SQLite store with SQL-file migrations and upsert helpers.
    """

    def __init__(self, db_path: Path, migrations_dir: Path):
        self.db_path = db_path
        self.migrations_dir = migrations_dir
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def migrate(self) -> None:
        self.migrations_dir.mkdir(parents=True, exist_ok=True)

        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            applied_rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
            applied = {row["version"] for row in applied_rows}

            migration_files = sorted(self.migrations_dir.glob("*.sql"))
            for migration_file in migration_files:
                version = migration_file.name.split("_", maxsplit=1)[0]
                if version in applied:
                    continue
                sql_script = migration_file.read_text(encoding="utf-8")
                conn.executescript(sql_script)
                conn.execute(
                    "INSERT INTO schema_migrations(version) VALUES (?)",
                    (version,),
                )
            conn.commit()

    def upsert_company(self, company: Dict[str, object]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO companies (ticker, name, sector, industry, updated_at)
                VALUES (:ticker, :name, :sector, :industry, :updated_at)
                ON CONFLICT(ticker) DO UPDATE SET
                    name = excluded.name,
                    sector = excluded.sector,
                    industry = excluded.industry,
                    updated_at = excluded.updated_at
                """,
                company,
            )
            conn.commit()

    def upsert_financial_snapshot(self, snapshot: Dict[str, object]) -> None:
        with self._connect() as conn:
            conn.execute(
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
                    :ticker,
                    :market_cap,
                    :beta,
                    :trailing_pe,
                    :price_to_book,
                    :debt_to_equity,
                    :profit_margin,
                    :latest_close,
                    :return_1m,
                    :return_3m,
                    :return_1y,
                    :volatility_1y,
                    :source_fundamentals,
                    :source_prices,
                    :updated_at
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
                snapshot,
            )
            conn.commit()

    def fetch_all_snapshots(self) -> Iterable[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
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
            ).fetchall()
