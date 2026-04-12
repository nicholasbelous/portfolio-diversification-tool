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

## Full-Load Checklist

1. Generate/refresh ticker universe cache (`sp500_reference.json`) if needed.
2. Run a one-time full backfill with `--force-refresh` so Postgres is guaranteed to be populated.
3. Run scheduled incremental refreshes without `--force-refresh` (daily/weekly).
4. Verify row counts and key coverage:

```sql
SELECT COUNT(*) AS companies FROM companies;
SELECT COUNT(*) AS snapshots FROM financial_snapshots;
SELECT COUNT(*) AS beta_populated
FROM financial_snapshots
WHERE beta IS NOT NULL;
```
