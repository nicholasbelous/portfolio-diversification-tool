import logging
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from app.db import PostgresStore, get_database_url
from app.models.requests import (
    PortfolioAnalyzeRequest,
    PortfolioCompareHistoryRequest,
    PortfolioOptimizeRequest,
    PortfolioProjectRequest,
)
from app.services.portfolio_strategy_service import PortfolioStrategyService

logger = logging.getLogger(__name__)


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
        logger.warning(f"Validation error in analyze_portfolio: {exc}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TimeoutError as exc:
        logger.error(f"Timeout in analyze_portfolio: {exc}")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Request timeout") from exc
    except MemoryError as exc:
        logger.error(f"Memory error in analyze_portfolio: {exc}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service temporarily unavailable") from exc
    except Exception as exc:
        logger.error(f"Unexpected error in analyze_portfolio: {exc}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error") from exc


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
        logger.warning(f"Validation error in optimize_portfolio: {exc}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TimeoutError as exc:
        logger.error(f"Timeout in optimize_portfolio: {exc}")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Request timeout") from exc
    except MemoryError as exc:
        logger.error(f"Memory error in optimize_portfolio: {exc}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service temporarily unavailable") from exc
    except Exception as exc:
        logger.error(f"Unexpected error in optimize_portfolio: {exc}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error") from exc


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
        logger.warning(f"Validation error in project_portfolio: {exc}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TimeoutError as exc:
        logger.error(f"Timeout in project_portfolio: {exc}")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Request timeout") from exc
    except MemoryError as exc:
        logger.error(f"Memory error in project_portfolio: {exc}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service temporarily unavailable") from exc
    except Exception as exc:
        logger.error(f"Unexpected error in project_portfolio: {exc}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error") from exc


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
        logger.warning(f"Validation error in compare_history: {exc}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TimeoutError as exc:
        logger.error(f"Timeout in compare_history: {exc}")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Request timeout") from exc
    except MemoryError as exc:
        logger.error(f"Memory error in compare_history: {exc}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service temporarily unavailable") from exc
    except Exception as exc:
        logger.error(f"Unexpected error in compare_history: {exc}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error") from exc
