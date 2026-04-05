from pathlib import Path

try:
    from app.db import SQLiteStore
except ModuleNotFoundError:  # pragma: no cover - allows running from repo root
    from backend.app.db import SQLiteStore


def main() -> None:
    app_root = Path(__file__).resolve().parent.parent
    db_path = app_root / "data" / "static" / "portfolio_data.db"
    migrations_dir = app_root / "db" / "migrations"
    SQLiteStore(db_path=db_path, migrations_dir=migrations_dir)
    print(f"Migrations applied to {db_path}")


if __name__ == "__main__":
    main()
