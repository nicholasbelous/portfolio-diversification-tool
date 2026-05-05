from types import SimpleNamespace

import numpy as np
import pandas as pd

from app.services.portfolio_strategy_service import PortfolioStrategyService


def _make_daily_returns(days: int = 260, seed: int = 7) -> pd.Series:
    rng = np.random.default_rng(seed)
    # Mild drift + realistic daily volatility for equity-like returns.
    samples = rng.normal(loc=0.0004, scale=0.012, size=days)
    index = pd.bdate_range("2025-01-01", periods=days)
    return pd.Series(samples, index=index, dtype=float)


def _service() -> PortfolioStrategyService:
    # ML projection helpers do not require store access.
    return PortfolioStrategyService(store=SimpleNamespace())


def test_projection_from_daily_includes_ml_forecast():
    svc = _service()
    daily = _make_daily_returns(days=280, seed=101)

    projection = svc._projection_from_daily(daily=daily, horizon_days=252, simulations=1200)

    assert projection["historical"] is not None
    assert projection["monte_carlo"] is not None
    ml = projection["ml_forecast"]
    assert ml is not None
    assert ml["method"] == "autoregressive_ridge_bootstrap"
    assert ml["training_samples"] > 0
    assert ml["validation_samples"] > 0
    assert ml["p10"] <= ml["p50"] <= ml["p90"]
    assert np.isfinite(float(ml["validation_mae_model"]))
    assert np.isfinite(float(ml["validation_mae_naive"]))


def test_projection_from_daily_is_deterministic_for_same_input():
    svc = _service()
    daily = _make_daily_returns(days=300, seed=2026)

    first = svc._projection_from_daily(daily=daily, horizon_days=63, simulations=900)
    second = svc._projection_from_daily(daily=daily, horizon_days=63, simulations=900)

    first_ml = first["ml_forecast"]
    second_ml = second["ml_forecast"]
    assert first_ml is not None and second_ml is not None
    assert first_ml["p50"] == second_ml["p50"]
    assert first_ml["p10"] == second_ml["p10"]
    assert first_ml["p90"] == second_ml["p90"]


def test_projection_from_daily_small_history_gracefully_disables_ml():
    svc = _service()
    # Below ML minimum training threshold.
    daily = _make_daily_returns(days=80, seed=11)

    projection = svc._projection_from_daily(daily=daily, horizon_days=63, simulations=800)

    assert projection["monte_carlo"] is not None
    assert projection["ml_forecast"] is None

