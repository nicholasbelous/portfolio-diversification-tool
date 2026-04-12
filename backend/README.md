## Database Setup (Postgres Only)

The backend now uses a single Postgres database path via `DATABASE_URL`.
Run the commands below from the `backend/` directory.

### 1) Set environment variable

```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/portfolio_diversification"
```

### 2) Run migrations

```bash
python -m app.db.migrate
```

### 3) Run financial pipeline

```bash
python -m app.data.company_financials_pipeline --from-sp500-reference --force-refresh
```

Optional override:

```bash
python -m app.data.company_financials_pipeline \
  --database-url "postgresql://postgres:postgres@localhost:5432/portfolio_diversification" \
  --from-sp500-reference
```
