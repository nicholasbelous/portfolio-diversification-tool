from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.db import PostgresStore, get_database_url
from app.models.requests import (
    PortfolioAnalyzeRequest,
    PortfolioCompareHistoryRequest,
    PortfolioOptimizeRequest,
    PortfolioProjectRequest,
)
from app.services.portfolio_strategy_service import PortfolioStrategyService


router = APIRouter(tags=["portfolio"])


@lru_cache(maxsize=1)
def _get_service() -> PortfolioStrategyService:
    app_root = Path(__file__).resolve().parents[2]
    store = PostgresStore(
        database_url=get_database_url(),
        migrations_dir=app_root / "db" / "migrations",
    )
    return PortfolioStrategyService(store=store)


@router.post("/portfolio/analyze")
def analyze_portfolio(payload: PortfolioAnalyzeRequest):
    try:
        data = _get_service().analyze_portfolio(payload.holdings)
        return {"data": data}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/portfolio/optimize")
def optimize_portfolio(payload: PortfolioOptimizeRequest):
    try:
        data = _get_service().optimize_portfolio(
            holdings=payload.holdings,
            max_changes=payload.max_changes,
            transaction_cost_rate=payload.transaction_cost_rate,
            include_sp500_additions=payload.include_sp500_additions,
            include_etfs=payload.include_etfs,
            candidate_limit=payload.candidate_limit,
            random_portfolios=payload.random_portfolios,
        )
        return {"data": data}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/portfolio/project")
def project_portfolio(payload: PortfolioProjectRequest):
    try:
        data = _get_service().project_portfolio(
            holdings=payload.holdings,
            horizon_months=payload.horizon_months,
            simulations=payload.simulations,
        )
        return {"data": data}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/portfolio/compare-history")
def compare_history(payload: PortfolioCompareHistoryRequest):
    try:
        data = _get_service().compare_portfolio_history(
            holdings=payload.holdings,
            optimized_weights=payload.optimized_weights,
            lookback_days=payload.lookback_days,
            include_benchmark=payload.include_benchmark,
        )
        return {"data": data}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
