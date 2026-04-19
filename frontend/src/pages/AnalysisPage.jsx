import { formatNumber, formatPct } from "../lib/format";
import InfoTip from "../ui/InfoTip";
import MetricCard from "../ui/MetricCard";
import ProjectionCard from "../ui/ProjectionCard";

const METRIC_EXPLANATIONS = {
  expected_return_annual:
    "Average daily return scaled to a year (252 trading days). It is an estimate, not a promise.",
  volatility_annual:
    "Annualized standard deviation of daily returns. Higher means larger expected swings.",
  sharpe_ratio:
    "Return per unit of volatility. Higher generally means better risk-adjusted performance.",
  beta_weighted:
    "Sensitivity to broad market movements. 1.0 roughly tracks the market, above 1.0 moves more.",
  max_drawdown_1y:
    "Largest peak-to-trough decline over the lookback period. Helps show downside pain during stress."
};

export default function AnalysisPage({
  analysis,
  topVolatility,
  maxChanges,
  onChangeMaxChanges,
  tradeCostRate,
  onChangeTradeCostRate,
  onBack,
  onOptimize,
  loading
}) {
  const sectorExposure = Object.entries(analysis?.metrics?.sector_exposure || {});

  return (
    <section className="page-content">
      <header className="page-header with-actions">
        <div>
          <p className="page-kicker">Step 2</p>
          <h2>Risk Diagnosis</h2>
          <p>
            This page explains how your current portfolio behaves today. Review this before generating an optimization
            recommendation.
          </p>
        </div>
        <button type="button" className="ghost-btn" onClick={onBack}>
          Back to Input
        </button>
      </header>

      <div className="metric-grid analysis-grid">
        <MetricCard
          label="Expected Annual Return"
          value={formatPct(analysis?.metrics?.expected_return_annual)}
          tooltip={METRIC_EXPLANATIONS.expected_return_annual}
        />
        <MetricCard
          label="Annual Volatility"
          value={formatPct(analysis?.metrics?.volatility_annual)}
          tooltip={METRIC_EXPLANATIONS.volatility_annual}
        />
        <MetricCard
          label="Sharpe Ratio"
          value={formatNumber(analysis?.metrics?.sharpe_ratio)}
          tooltip={METRIC_EXPLANATIONS.sharpe_ratio}
        />
        <MetricCard
          label="Weighted Beta"
          value={formatNumber(analysis?.metrics?.beta_weighted)}
          tooltip={METRIC_EXPLANATIONS.beta_weighted}
        />
        <MetricCard
          label="Max Drawdown (1Y)"
          value={formatPct(analysis?.metrics?.max_drawdown_1y)}
          tooltip={METRIC_EXPLANATIONS.max_drawdown_1y}
          tone="warning"
        />
        <MetricCard
          label="Holdings Count"
          value={formatNumber(analysis?.holdings?.length || 0, 0)}
          tooltip="Number of holdings with valid financial and price data used in analysis."
        />
      </div>

      <div className="panel-grid">
        <article className="surface-card">
          <div className="section-head">
            <h3>Forward-Looking Scenarios</h3>
            <InfoTip
              label="Scenario projections"
              text="These ranges are scenario envelopes from historical behavior and simulation assumptions. They help frame uncertainty, not certainty."
            />
          </div>
          <div className="projection-stack">
            <ProjectionCard title="3 Month Outlook" projection={analysis?.projections?.horizon_3m} />
            <ProjectionCard title="1 Year Outlook" projection={analysis?.projections?.horizon_1y} />
          </div>
        </article>

        <aside className="surface-card side-card">
          <div className="section-head">
            <h3>Sector Exposure</h3>
            <InfoTip
              label="Sector exposure"
              text="Concentration risk appears when one sector has a large share of total weight. More balance can reduce downside clustering."
            />
          </div>
          {sectorExposure.length ? (
            <div className="sector-stack">
              {sectorExposure.slice(0, 8).map(([sector, value]) => (
                <div key={sector} className="sector-row">
                  <span>{sector}</span>
                  <div className="sector-bar">
                    <div style={{ width: `${Math.max(3, Math.min(100, value * 100))}%` }} />
                  </div>
                  <strong>{formatPct(value)}</strong>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted">Sector data unavailable for this input set.</p>
          )}
        </aside>
      </div>

      <div className="panel-grid">
        <article className="surface-card">
          <div className="section-head">
            <h3>Optimization Controls</h3>
            <InfoTip
              label="Optimization controls"
              text="Max changes controls turnover. Trade cost rate penalizes large reshuffles and keeps recommendations practical."
            />
          </div>

          <div className="optimizer-controls">
            <label>
              Max Add/Remove Changes
              <input
                type="number"
                min="1"
                max="20"
                value={maxChanges}
                onChange={(event) => onChangeMaxChanges(event.target.value)}
              />
            </label>
            <label>
              Trade Cost Rate
              <input
                type="number"
                min="0"
                max="0.05"
                step="0.0001"
                value={tradeCostRate}
                onChange={(event) => onChangeTradeCostRate(event.target.value)}
              />
            </label>
          </div>

          <div className="action-row dual">
            <p className="muted">Higher cost and lower max changes usually produce more conservative recommendations.</p>
            <button type="button" onClick={onOptimize} disabled={loading}>
              {loading ? "Building Optimization..." : "Generate Optimization Plan"}
            </button>
          </div>
        </article>

        <aside className="surface-card side-card">
          <div className="section-head">
            <h3>Volatility Reference</h3>
            <InfoTip
              label="Volatility reference"
              text="A quick look at higher-volatility names in your current universe for context while reviewing risk metrics."
            />
          </div>
          {topVolatility?.length ? (
            <ul className="volatility-list">
              {topVolatility.map((row) => (
                <li key={row.ticker}>
                  <div>
                    <strong>{row.ticker}</strong>
                    <span>{row.name}</span>
                  </div>
                  <p>{formatPct(row.volatility_1y)}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Volatility reference list loads after a successful analysis.</p>
          )}
        </aside>
      </div>
    </section>
  );
}
