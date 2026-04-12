from datetime import date
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from app.db import PostgresStore, get_database_url


router = APIRouter(tags=["financials"])


@lru_cache(maxsize=1)
def _get_store() -> PostgresStore:
    app_root = Path(__file__).resolve().parents[2]
    return PostgresStore(
        database_url=get_database_url(),
        migrations_dir=app_root / "db" / "migrations",
    )


@router.get("/financials/top-volatility")
def get_top_volatility(
    limit: int = Query(default=25, ge=1, le=200),
):
    rows = _get_store().fetch_top_snapshots(metric="volatility_1y", limit=limit)
    return {"metric": "volatility_1y", "count": len(rows), "items": rows}


@router.get("/financials/top-beta")
def get_top_beta(
    limit: int = Query(default=25, ge=1, le=200),
):
    rows = _get_store().fetch_top_snapshots(metric="beta", limit=limit)
    return {"metric": "beta", "count": len(rows), "items": rows}


@router.get("/financials/{ticker}")
def get_financial_snapshot(ticker: str):
    row = _get_store().fetch_snapshot_by_ticker(ticker=ticker)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Ticker not found: {ticker.upper()}")
    return row


@router.get("/financials/{ticker}/history")
def get_ticker_history(
    ticker: str,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=1500, ge=1, le=5000),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be <= end_date")

    rows = _get_store().fetch_price_history(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"No history found for {ticker.upper()}")

    return {"ticker": ticker.upper(), "count": len(rows), "items": rows}
