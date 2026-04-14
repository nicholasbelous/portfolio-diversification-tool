from pathlib import Path

from app.db import PostgresStore, get_database_url, redact_database_url


def main() -> None:
    app_root = Path(__file__).resolve().parent.parent
    migrations_dir = app_root / "db" / "migrations"
    database_url = get_database_url()
    PostgresStore(database_url=database_url, migrations_dir=migrations_dir)
    print(f"Migrations applied to {redact_database_url(database_url)}")


if __name__ == "__main__":
    main()
