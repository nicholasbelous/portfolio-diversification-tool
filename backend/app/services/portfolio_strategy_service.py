from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd

from app.db import PostgresStore
from app.models.requests import PortfolioHoldingInput


ETF_CANDIDATES = ["SPY", "QQQ", "VTI", "IWM", "DIA"]


@dataclass
class NormalizedPortfolio:
    weights: Dict[str, float]
    mode: str
    total_value: float
    warnings: List[str]


class PortfolioStrategyService:
    def __init__(self, store: PostgresStore):
        self.store = store

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _normalize_portfolio(self, holdings: Sequence[PortfolioHoldingInput]) -> NormalizedPortfolio:
        warnings: List[str] = []
        ticker_to_amount: Dict[str, float] = {}
        ticker_to_weight: Dict[str, float] = {}

        all_amounts = True
        all_weights = True
        for row in holdings:
            ticker = row.ticker.strip().upper()
            if not ticker:
                continue
            if row.amount is None:
                all_amounts = False
            if row.weight is None:
                all_weights = False

            if row.amount is not None:
                ticker_to_amount[ticker] = ticker_to_amount.get(ticker, 0.0) + float(row.amount)
            if row.weight is not None:
                ticker_to_weight[ticker] = ticker_to_weight.get(ticker, 0.0) + float(row.weight)

        if not ticker_to_amount and not ticker_to_weight:
            raise ValueError("No valid holdings provided.")

        if all_amounts and ticker_to_amount:
            total = float(sum(max(v, 0.0) for v in ticker_to_amount.values()))
            if total <= 0:
                raise ValueError("Holdings total amount must be greater than zero.")
            normalized = {t: max(v, 0.0) / total for t, v in ticker_to_amount.items()}
            return NormalizedPortfolio(
                weights=normalized,
                mode="amount",
                total_value=total,
                warnings=warnings,
            )

        if all_weights and ticker_to_weight:
            total = float(sum(max(v, 0.0) for v in ticker_to_weight.values()))
            if total <= 0:
                raise ValueError("Holdings total weight must be greater than zero.")
            normalized = {t: max(v, 0.0) / total for t, v in ticker_to_weight.items()}
            return NormalizedPortfolio(
                weights=normalized,
                mode="weight",
                total_value=1.0,
                warnings=warnings,
            )

        # Mixed mode fallback: prioritize amounts when present.
        if ticker_to_amount:
            warnings.append(
                "Mixed amount/weight input detected; optimization used amount-based holdings where provided."
            )
            total = float(sum(max(v, 0.0) for v in ticker_to_amount.values()))
            if total <= 0:
                raise ValueError("Holdings total amount must be greater than zero.")
            normalized = {t: max(v, 0.0) / total for t, v in ticker_to_amount.items()}
            return NormalizedPortfolio(
                weights=normalized,
                mode="amount",
                total_value=total,
                warnings=warnings,
            )

        warnings.append("Mixed amount/weight input detected; optimization used normalized weights.")
        total = float(sum(max(v, 0.0) for v in ticker_to_weight.values()))
        normalized = {t: max(v, 0.0) / total for t, v in ticker_to_weight.items()}
        return NormalizedPortfolio(weights=normalized, mode="weight", total_value=1.0, warnings=warnings)

    def _snapshot_map(self, tickers: Sequence[str]) -> Dict[str, Dict[str, Any]]:
        rows = self.store.fetch_snapshots_by_tickers(list(tickers))
        return {str(row["ticker"]).upper(): dict(row) for row in rows}

    def _build_returns_matrix(self, tickers: Sequence[str], min_history: int = 180) -> pd.DataFrame:
        rows = self.store.fetch_price_history_for_tickers(list(tickers))
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        if df.empty:
            return pd.DataFrame()

        df["ticker"] = df["ticker"].str.upper()
        price = (
            df.pivot(index="trading_date", columns="ticker", values="close")
            .sort_index()
            .astype(float)
            .ffill()
        )
        returns = price.pct_change().replace([np.inf, -np.inf], np.nan)
        valid_cols = [col for col in returns.columns if returns[col].dropna().shape[0] >= min_history]
        if not valid_cols:
            return pd.DataFrame()
        returns = returns[valid_cols]
        returns = returns.dropna(how="any")
        return returns

    @staticmethod
    def _portfolio_daily_returns(returns_matrix: pd.DataFrame, weights: Dict[str, float]) -> pd.Series:
        common = [ticker for ticker in weights.keys() if ticker in returns_matrix.columns]
        if not common:
            return pd.Series(dtype=float)
        vec = np.array([weights[t] for t in common], dtype=float)
        if vec.sum() <= 0:
            return pd.Series(dtype=float)
        vec = vec / vec.sum()
        series = returns_matrix[common].to_numpy() @ vec
        return pd.Series(series, index=returns_matrix.index, dtype=float)

    @staticmethod
    def _max_drawdown(daily_returns: pd.Series) -> float | None:
        if daily_returns.empty:
            return None
        curve = (1.0 + daily_returns).cumprod()
        peak = curve.cummax()
        drawdown = curve / peak - 1.0
        return float(drawdown.min())

    @staticmethod
    def _sector_exposure(weights: Dict[str, float], snapshots: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
        exposure: Dict[str, float] = {}
        for ticker, weight in weights.items():
            row = snapshots.get(ticker)
            if row is None:
                continue
            sector = str(row.get("sector") or "Unknown")
            exposure[sector] = exposure.get(sector, 0.0) + float(weight)
        return {k: round(v, 6) for k, v in sorted(exposure.items(), key=lambda x: x[1], reverse=True)}

    def _portfolio_metrics(
        self,
        weights: Dict[str, float],
        returns_matrix: pd.DataFrame,
        snapshots: Dict[str, Dict[str, Any]],
        transaction_cost_rate: float = 0.0,
        baseline_weights: Dict[str, float] | None = None,
    ) -> Dict[str, Any]:
        daily = self._portfolio_daily_returns(returns_matrix, weights)
        if daily.empty:
            return {
                "expected_return_annual": None,
                "volatility_annual": None,
                "sharpe_ratio": None,
                "max_drawdown_1y": None,
                "beta_weighted": None,
                "sector_exposure": self._sector_exposure(weights, snapshots),
            }

        mean_daily = float(daily.mean())
        std_daily = float(daily.std(ddof=1))
        expected_return_annual = mean_daily * 252.0
        volatility_annual = std_daily * (252.0**0.5)
        sharpe = expected_return_annual / volatility_annual if volatility_annual > 0 else None

        beta_num = 0.0
        beta_den = 0.0
        for ticker, weight in weights.items():
            beta = self._safe_float(snapshots.get(ticker, {}).get("beta"))
            if beta is None:
                continue
            beta_num += weight * beta
            beta_den += weight
        beta_weighted = beta_num / beta_den if beta_den > 0 else None

        metrics = {
            "expected_return_annual": expected_return_annual,
            "volatility_annual": volatility_annual,
            "sharpe_ratio": sharpe,
            "max_drawdown_1y": self._max_drawdown(daily),
            "beta_weighted": beta_weighted,
            "sector_exposure": self._sector_exposure(weights, snapshots),
        }
        if baseline_weights is not None:
            turnover = float(
                sum(abs(weights.get(t, 0.0) - baseline_weights.get(t, 0.0)) for t in set(weights) | set(baseline_weights))
            )
            metrics["turnover"] = turnover
            metrics["estimated_trade_cost"] = turnover * transaction_cost_rate
        return metrics

    @staticmethod
    def _projection_from_daily(daily: pd.Series, horizon_days: int, simulations: int = 3000) -> Dict[str, Any]:
        if daily.empty:
            return {
                "horizon_days": horizon_days,
                "historical": None,
                "monte_carlo": None,
            }

        hist = (1.0 + daily).rolling(window=horizon_days).apply(np.prod, raw=True) - 1.0
        hist = hist.dropna()
        hist_summary = None
        if not hist.empty:
            hist_summary = {
                "p10": float(hist.quantile(0.10)),
                "p50": float(hist.quantile(0.50)),
                "p90": float(hist.quantile(0.90)),
                "mean": float(hist.mean()),
            }

        mean_daily = float(daily.mean())
        std_daily = float(daily.std(ddof=1))
        if std_daily <= 0:
            sims_terminal = np.full(shape=(simulations,), fill_value=(1.0 + mean_daily) ** horizon_days - 1.0)
        else:
            rng = np.random.default_rng(42)
            sim_daily = rng.normal(loc=mean_daily, scale=std_daily, size=(simulations, horizon_days))
            sim_daily = np.clip(sim_daily, -0.95, 2.0)
            sims_terminal = np.prod(1.0 + sim_daily, axis=1) - 1.0

        mc_summary = {
            "p10": float(np.quantile(sims_terminal, 0.10)),
            "p50": float(np.quantile(sims_terminal, 0.50)),
            "p90": float(np.quantile(sims_terminal, 0.90)),
            "mean": float(np.mean(sims_terminal)),
        }
        return {
            "horizon_days": horizon_days,
            "historical": hist_summary,
            "monte_carlo": mc_summary,
        }

    def analyze_portfolio(self, holdings: Sequence[PortfolioHoldingInput]) -> Dict[str, Any]:
        normalized = self._normalize_portfolio(holdings)
        current_tickers = sorted(normalized.weights.keys())
        snapshots = self._snapshot_map(current_tickers)
        available_weights = {t: w for t, w in normalized.weights.items() if t in snapshots}
        missing = sorted(set(normalized.weights) - set(available_weights))
        warnings = list(normalized.warnings)
        if missing:
            warnings.append(f"Missing snapshot data for: {', '.join(missing)}")
        if not available_weights:
            raise ValueError("None of the provided tickers were found in the financial snapshot table.")

        weight_total = sum(available_weights.values())
        available_weights = {t: w / weight_total for t, w in available_weights.items()}

        returns = self._build_returns_matrix(list(available_weights.keys()))
        metrics = self._portfolio_metrics(available_weights, returns, snapshots)
        daily = self._portfolio_daily_returns(returns, available_weights)
        projections = {
            "horizon_3m": self._projection_from_daily(daily, horizon_days=63),
            "horizon_1y": self._projection_from_daily(daily, horizon_days=252),
        }

        holdings_out = []
        for ticker, weight in sorted(available_weights.items()):
            row = snapshots[ticker]
            holdings_out.append(
                {
                    "ticker": ticker,
                    "weight": float(weight),
                    "name": row.get("name"),
                    "sector": row.get("sector"),
                    "beta": self._safe_float(row.get("beta")),
                    "volatility_1y": self._safe_float(row.get("volatility_1y")),
                    "return_1y": self._safe_float(row.get("return_1y")),
                }
            )

        return {
            "mode": normalized.mode,
            "total_value_input": normalized.total_value,
            "holdings": holdings_out,
            "metrics": metrics,
            "projections": projections,
            "warnings": warnings,
        }

    def _candidate_universe(
        self,
        current_tickers: Sequence[str],
        include_sp500_additions: bool,
        include_etfs: bool,
        candidate_limit: int,
    ) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
        current = {ticker.upper() for ticker in current_tickers}
        snapshots = {row["ticker"].upper(): dict(row) for row in self.store.fetch_snapshots_by_tickers(list(current))}

        if include_sp500_additions:
            for row in self.store.fetch_candidate_snapshots_by_market_cap(limit=candidate_limit):
                snapshots[str(row["ticker"]).upper()] = dict(row)

        if include_etfs:
            etf_rows = self.store.fetch_snapshots_by_tickers(ETF_CANDIDATES)
            for row in etf_rows:
                snapshots[str(row["ticker"]).upper()] = dict(row)

        return sorted(snapshots.keys()), snapshots

    @staticmethod
    def _count_changes(
        baseline: Dict[str, float],
        candidate: Dict[str, float],
        threshold: float = 0.01,
    ) -> Dict[str, Any]:
        all_tickers = set(baseline) | set(candidate)
        changed = [
            ticker
            for ticker in all_tickers
            if abs(candidate.get(ticker, 0.0) - baseline.get(ticker, 0.0)) >= threshold
        ]
        additions = [
            ticker for ticker in all_tickers if baseline.get(ticker, 0.0) < threshold and candidate.get(ticker, 0.0) >= threshold
        ]
        removals = [
            ticker for ticker in all_tickers if baseline.get(ticker, 0.0) >= threshold and candidate.get(ticker, 0.0) < threshold
        ]
        return {
            "changed": sorted(changed),
            "additions": sorted(additions),
            "removals": sorted(removals),
            "add_remove_count": len(additions) + len(removals),
            "count": len(changed),
        }

    def optimize_portfolio(
        self,
        holdings: Sequence[PortfolioHoldingInput],
        max_changes: int = 5,
        transaction_cost_rate: float = 0.0015,
        include_sp500_additions: bool = True,
        include_etfs: bool = True,
        candidate_limit: int = 120,
        random_portfolios: int = 3500,
    ) -> Dict[str, Any]:
        normalized = self._normalize_portfolio(holdings)
        current_weights = normalized.weights
        universe, snapshots = self._candidate_universe(
            current_tickers=list(current_weights.keys()),
            include_sp500_additions=include_sp500_additions,
            include_etfs=include_etfs,
            candidate_limit=candidate_limit,
        )

        current_valid = {t: w for t, w in current_weights.items() if t in snapshots}
        if not current_valid:
            raise ValueError("None of the provided holdings are available in current snapshot data.")
        current_weights = {t: w / sum(current_valid.values()) for t, w in current_valid.items()}

        returns = self._build_returns_matrix(universe)
        if returns.empty:
            raise ValueError("Insufficient historical data found in price_history_daily for optimization.")

        valid_universe = [ticker for ticker in returns.columns if ticker in snapshots]
        returns = returns[valid_universe].dropna(how="any")
        if returns.shape[0] < 120 or returns.shape[1] < 2:
            raise ValueError("Not enough overlapping return history for optimization.")

        w0 = np.array([current_weights.get(ticker, 0.0) for ticker in valid_universe], dtype=float)
        if w0.sum() <= 0:
            raise ValueError("No valid current holdings remained after data alignment.")
        w0 = w0 / w0.sum()

        mu = returns.mean(axis=0).to_numpy() * 252.0
        cov = returns.cov().to_numpy() * 252.0
        current_idx = np.where(w0 > 1e-12)[0]
        non_current_idx = np.where(w0 <= 1e-12)[0]

        def objective(w: np.ndarray) -> Tuple[float, Dict[str, Any]]:
            port_return = float(np.dot(w, mu))
            port_vol = float(np.sqrt(max(np.dot(w, cov @ w), 1e-12)))
            sharpe = port_return / port_vol if port_vol > 0 else -999.0
            turnover = float(np.abs(w - w0).sum())

            baseline_map = {valid_universe[i]: float(w0[i]) for i in range(len(valid_universe))}
            candidate_map = {valid_universe[i]: float(w[i]) for i in range(len(valid_universe))}
            changes = self._count_changes(baseline_map, candidate_map)
            if changes["add_remove_count"] > max_changes:
                return -1e9, {
                    "expected_return_annual": port_return,
                    "volatility_annual": port_vol,
                    "sharpe_ratio": sharpe,
                    "turnover": turnover,
                    "estimated_trade_cost": turnover * transaction_cost_rate,
                    "change_penalty": changes["add_remove_count"] - max_changes,
                    "changes": changes,
                }

            estimated_cost = turnover * transaction_cost_rate
            net_return = port_return - estimated_cost
            score = sharpe + 0.2 * net_return - 0.35 * turnover
            return score, {
                "expected_return_annual": port_return,
                "volatility_annual": port_vol,
                "sharpe_ratio": sharpe,
                "turnover": turnover,
                "estimated_trade_cost": estimated_cost,
                "change_penalty": 0,
                "changes": changes,
            }

        best_w = w0.copy()
        best_score, best_stats = objective(best_w)
        rng = np.random.default_rng(2026)

        candidate_pool = non_current_idx.copy()
        if candidate_pool.size > 0:
            candidate_scores = mu[candidate_pool]
            ranked = candidate_pool[np.argsort(candidate_scores)[::-1]]
            candidate_pool = ranked[: max(20, min(120, ranked.size))]

        for _ in range(random_portfolios):
            w = np.zeros_like(w0)

            # Keep existing holdings anchored, then optionally add a small number of new names.
            k_new = int(rng.integers(0, min(max_changes, len(candidate_pool)) + 1)) if len(candidate_pool) else 0
            chosen_new = (
                rng.choice(candidate_pool, size=k_new, replace=False).tolist() if k_new > 0 else []
            )
            active = list(current_idx) + chosen_new
            if not active:
                continue

            alpha = np.array(
                [
                    1.0 + (25.0 * w0[idx] if idx in current_idx else 0.6)
                    for idx in active
                ],
                dtype=float,
            )
            sample = rng.dirichlet(alpha)
            for pos, idx in enumerate(active):
                w[idx] = sample[pos]
            w = np.clip(w, 0.0, None)
            if w.sum() <= 0:
                continue
            w = w / w.sum()

            score, stats = objective(w)
            if score > best_score:
                best_score = score
                best_w = w
                best_stats = stats

        current_map = {valid_universe[i]: float(w0[i]) for i in range(len(valid_universe))}
        optimized_map = {valid_universe[i]: float(best_w[i]) for i in range(len(valid_universe))}

        current_metrics = self._portfolio_metrics(
            weights=current_map,
            returns_matrix=returns,
            snapshots=snapshots,
            transaction_cost_rate=transaction_cost_rate,
            baseline_weights=current_map,
        )
        optimized_metrics = self._portfolio_metrics(
            weights=optimized_map,
            returns_matrix=returns,
            snapshots=snapshots,
            transaction_cost_rate=transaction_cost_rate,
            baseline_weights=current_map,
        )

        current_daily = self._portfolio_daily_returns(returns, current_map)
        optimized_daily = self._portfolio_daily_returns(returns, optimized_map)
        projections = {
            "current": {
                "horizon_3m": self._projection_from_daily(current_daily, horizon_days=63),
                "horizon_1y": self._projection_from_daily(current_daily, horizon_days=252),
            },
            "optimized": {
                "horizon_3m": self._projection_from_daily(optimized_daily, horizon_days=63),
                "horizon_1y": self._projection_from_daily(optimized_daily, horizon_days=252),
            },
        }

        changes = self._count_changes(current_map, optimized_map)
        recommendations = []
        for ticker in sorted(changes["changed"]):
            old_w = current_map.get(ticker, 0.0)
            new_w = optimized_map.get(ticker, 0.0)
            delta = new_w - old_w
            action = "hold"
            if delta > 0.001:
                action = "buy"
            elif delta < -0.001:
                action = "sell"

            rec = {
                "ticker": ticker,
                "action": action,
                "current_weight": old_w,
                "target_weight": new_w,
                "delta_weight": delta,
                "name": snapshots.get(ticker, {}).get("name"),
                "sector": snapshots.get(ticker, {}).get("sector"),
            }
            if normalized.mode == "amount":
                rec["current_amount"] = old_w * normalized.total_value
                rec["target_amount"] = new_w * normalized.total_value
                rec["delta_amount"] = rec["target_amount"] - rec["current_amount"]
            recommendations.append(rec)

        top_targets = sorted(
            [{"ticker": t, "weight": w, "name": snapshots.get(t, {}).get("name")} for t, w in optimized_map.items()],
            key=lambda x: x["weight"],
            reverse=True,
        )[:15]

        insights = []
        if (
            current_metrics.get("volatility_annual") is not None
            and optimized_metrics.get("volatility_annual") is not None
        ):
            vol_change = optimized_metrics["volatility_annual"] - current_metrics["volatility_annual"]
            insights.append(
                f"Estimated annual volatility change: {vol_change * 100:+.2f}%."
            )
        if (
            current_metrics.get("expected_return_annual") is not None
            and optimized_metrics.get("expected_return_annual") is not None
        ):
            ret_change = optimized_metrics["expected_return_annual"] - current_metrics["expected_return_annual"]
            insights.append(
                f"Estimated annual return change (before trade costs): {ret_change * 100:+.2f}%."
            )
        insights.append(
            f"Turnover was constrained with max {max_changes} add/remove changes and {transaction_cost_rate*100:.2f}% trade cost."
        )

        return {
            "mode": normalized.mode,
            "total_value_input": normalized.total_value,
            "objective": "max_sharpe_low_turnover",
            "settings": {
                "max_changes": max_changes,
                "transaction_cost_rate": transaction_cost_rate,
                "candidate_limit": candidate_limit,
                "random_portfolios": random_portfolios,
                "include_sp500_additions": include_sp500_additions,
                "include_etfs": include_etfs,
            },
            "current_metrics": current_metrics,
            "optimized_metrics": optimized_metrics,
            "impact": {
                "return_annual_delta": (
                    None
                    if current_metrics["expected_return_annual"] is None or optimized_metrics["expected_return_annual"] is None
                    else optimized_metrics["expected_return_annual"] - current_metrics["expected_return_annual"]
                ),
                "volatility_annual_delta": (
                    None
                    if current_metrics["volatility_annual"] is None or optimized_metrics["volatility_annual"] is None
                    else optimized_metrics["volatility_annual"] - current_metrics["volatility_annual"]
                ),
                "sharpe_delta": (
                    None
                    if current_metrics["sharpe_ratio"] is None or optimized_metrics["sharpe_ratio"] is None
                    else optimized_metrics["sharpe_ratio"] - current_metrics["sharpe_ratio"]
                ),
                "turnover": optimized_metrics.get("turnover"),
                "estimated_trade_cost": optimized_metrics.get("estimated_trade_cost"),
            },
            "projections": projections,
            "optimized_portfolio": top_targets,
            "recommended_changes": recommendations,
            "change_summary": changes,
            "optimizer_diagnostics": {
                "best_score": best_score,
                "best_stats": best_stats,
            },
            "insights": insights,
            "warnings": normalized.warnings,
        }

    def project_portfolio(
        self,
        holdings: Sequence[PortfolioHoldingInput],
        horizon_months: int = 12,
        simulations: int = 3000,
    ) -> Dict[str, Any]:
        normalized = self._normalize_portfolio(holdings)
        snapshots = self._snapshot_map(list(normalized.weights.keys()))
        available = {t: w for t, w in normalized.weights.items() if t in snapshots}
        if not available:
            raise ValueError("None of the provided holdings were found in snapshot data.")
        available = {t: w / sum(available.values()) for t, w in available.items()}

        returns = self._build_returns_matrix(list(available.keys()))
        daily = self._portfolio_daily_returns(returns, available)
        horizon_days = int(round(horizon_months * 21))
        projection = self._projection_from_daily(daily, horizon_days=horizon_days, simulations=simulations)
        metrics = self._portfolio_metrics(available, returns, snapshots)
        return {
            "mode": normalized.mode,
            "total_value_input": normalized.total_value,
            "horizon_months": horizon_months,
            "projection": projection,
            "metrics": metrics,
            "warnings": normalized.warnings,
        }
