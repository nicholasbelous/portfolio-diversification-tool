from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import portfolio as portfolio_routes


class _FakePortfolioService:
    def analyze_portfolio(self, holdings):
        return {
            "mode": "amount",
            "total_value_input": 10000.0,
            "holdings": [],
            "metrics": {},
            "projections": {
                "horizon_3m": {
                    "horizon_days": 63,
                    "historical": {"p10": -0.1, "p50": 0.02, "p90": 0.08, "mean": 0.01},
                    "monte_carlo": {"p10": -0.12, "p50": 0.03, "p90": 0.10, "mean": 0.02},
                    "ml_forecast": {
                        "method": "autoregressive_ridge_bootstrap",
                        "p10": -0.11,
                        "p50": 0.025,
                        "p90": 0.09,
                    },
                },
                "horizon_1y": {
                    "horizon_days": 252,
                    "historical": {"p10": -0.2, "p50": 0.08, "p90": 0.25, "mean": 0.07},
                    "monte_carlo": {"p10": -0.25, "p50": 0.1, "p90": 0.3, "mean": 0.09},
                    "ml_forecast": {
                        "method": "autoregressive_ridge_bootstrap",
                        "p10": -0.2,
                        "p50": 0.09,
                        "p90": 0.26,
                    },
                },
            },
            "warnings": [],
        }

    def project_portfolio(self, holdings, horizon_months, simulations):
        return {
            "mode": "amount",
            "total_value_input": 10000.0,
            "horizon_months": horizon_months,
            "projection": {
                "horizon_days": horizon_months * 21,
                "historical": {"p10": -0.2, "p50": 0.08, "p90": 0.25, "mean": 0.07},
                "monte_carlo": {"p10": -0.25, "p50": 0.1, "p90": 0.3, "mean": 0.09},
                "ml_forecast": {
                    "method": "autoregressive_ridge_bootstrap",
                    "p10": -0.2,
                    "p50": 0.09,
                    "p90": 0.26,
                },
            },
            "metrics": {},
            "warnings": [],
        }

    def optimize_portfolio(self, **kwargs):
        return {"warnings": [], "optimized_weights": []}

    def compare_portfolio_history(self, **kwargs):
        return {"series": {"current": [], "optimized": [], "benchmark": []}, "warnings": []}


def test_analyze_endpoint_exposes_ml_forecast(monkeypatch):
    monkeypatch.setattr(portfolio_routes, "_get_service", lambda: _FakePortfolioService())
    client = TestClient(app)

    payload = {"holdings": [{"ticker": "AAPL", "amount": 7000}, {"ticker": "MSFT", "amount": 3000}]}
    response = client.post("/api/v1/portfolio/analyze", json=payload)

    assert response.status_code == 200
    body = response.json()
    ml = body["data"]["projections"]["horizon_1y"]["ml_forecast"]
    assert ml is not None
    assert ml["method"] == "autoregressive_ridge_bootstrap"


def test_project_endpoint_exposes_ml_forecast(monkeypatch):
    monkeypatch.setattr(portfolio_routes, "_get_service", lambda: _FakePortfolioService())
    client = TestClient(app)

    payload = {
        "holdings": [{"ticker": "AAPL", "amount": 7000}, {"ticker": "MSFT", "amount": 3000}],
        "horizon_months": 12,
        "simulations": 1200,
    }
    response = client.post("/api/v1/portfolio/project", json=payload)

    assert response.status_code == 200
    body = response.json()
    ml = body["data"]["projection"]["ml_forecast"]
    assert ml is not None
    assert ml["method"] == "autoregressive_ridge_bootstrap"

