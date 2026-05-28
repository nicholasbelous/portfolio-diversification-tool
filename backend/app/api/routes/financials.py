import logging
from datetime import date
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status

from app.db import PostgresStore, get_database_url

logger = logging.getLogger(__name__)


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
    try:
        rows = _get_store().fetch_top_snapshots(metric="volatility_1y", limit=limit)
        return {"metric": "volatility_1y", "count": len(rows), "items": rows}
    except Exception as exc:
        logger.error(f"Error fetching top volatility: {exc}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch data") from exc


@router.get("/financials/top-beta")
def get_top_beta(
    limit: int = Query(default=25, ge=1, le=200),
):
    try:
        rows = _get_store().fetch_top_snapshots(metric="beta", limit=limit)
        return {"metric": "beta", "count": len(rows), "items": rows}
    except Exception as exc:
        logger.error(f"Error fetching top beta: {exc}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch data") from exc


@router.get("/financials/{ticker}")
def get_financial_snapshot(ticker: str):
    try:
        row = _get_store().fetch_snapshot_by_ticker(ticker=ticker)
        if row is None:
            logger.warning(f"Ticker not found: {ticker.upper()}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Ticker not found: {ticker.upper()}")
        return row
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error fetching snapshot for {ticker}: {exc}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch data") from exc


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
