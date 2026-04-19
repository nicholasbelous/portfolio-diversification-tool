import { formatMoney, formatNumber, formatPct } from "../lib/format";
import InfoTip from "../ui/InfoTip";
import MetricCard from "../ui/MetricCard";
import ProjectionCard from "../ui/ProjectionCard";
import PerformanceChart from "../ui/PerformanceChart";

function impactTone(value, invert = false) {
  if (value == null || Number.isNaN(value)) {
    return "neutral";
  }
  const positive = invert ? value < 0 : value > 0;
  return positive ? "good" : "warning";
}

export default function OptimizationPage({
  optimization,
  historyCompare,
  chartRange,
  onChangeChartRange,
  onBack,
  onStartOver
}) {
  const optimizedVsCurrent = historyCompare?.summary?.optimized_minus_current;

  return (
    <section className="page-content">
      <header className="page-header with-actions">
        <div>
          <p className="page-kicker">Step 3</p>
          <h2>Optimization Plan</h2>
          <p>
            Compare your current portfolio to the recommended target, review practical trade actions, and validate the
            risk/return tradeoff visually.
          </p>
        </div>
        <div className="header-actions">
          <button type="button" className="ghost-btn" onClick={onBack}>
            Back to Analysis
          </button>
          <button type="button" className="ghost-btn" onClick={onStartOver}>
            Start Over
          </button>
        </div>
      </header>

      <div className="compare-grid">
        <MetricCard
          label="Return Delta (Annual)"
          value={formatPct(optimization?.impact?.return_annual_delta)}
          tooltip="Optimized expected annual return minus current expected annual return (before realized market uncertainty)."
          tone={impactTone(optimization?.impact?.return_annual_delta)}
        />
        <MetricCard
          label="Volatility Delta"
          value={formatPct(optimization?.impact?.volatility_annual_delta)}
          tooltip="Optimized annual volatility minus current annual volatility. Lower is usually preferred."
          tone={impactTone(optimization?.impact?.volatility_annual_delta, true)}
        />
        <MetricCard
          label="Sharpe Delta"
          value={formatNumber(optimization?.impact?.sharpe_delta)}
          tooltip="Difference in risk-adjusted return efficiency between optimized and current portfolio."
          tone={impactTone(optimization?.impact?.sharpe_delta)}
        />
        <MetricCard
          label="Estimated Turnover"
          value={formatPct(optimization?.impact?.turnover)}
          tooltip="Sum of absolute weight changes required to execute this rebalance."
          tone="warning"
        />
        <MetricCard
          label="Estimated Trade Cost"
          value={formatPct(optimization?.impact?.estimated_trade_cost)}
          tooltip="Turnover multiplied by the configured transaction-cost rate assumption."
        />
        <MetricCard
          label="Allowed Add/Remove Changes"
          value={formatNumber(optimization?.settings?.max_changes, 0)}
          tooltip="Maximum number of new positions plus removed positions allowed by the optimizer."
        />
      </div>

      <PerformanceChart
        historyCompare={historyCompare}
        chartRange={chartRange}
        onChangeRange={onChangeChartRange}
      />

      <article className="surface-card realism-card">
        <div className="section-head">
          <h3>Realism Check</h3>
          <InfoTip
            label="Realism check"
            text="Optimization is model-based. Realized returns can differ due to regime shifts, liquidity changes, and transaction execution."
          />
        </div>
        <p>
          Historical chart result (optimized minus current):
          <strong className={optimizedVsCurrent != null && optimizedVsCurrent >= 0 ? "text-good" : "text-warning"}>
            {` ${formatPct(optimizedVsCurrent)}`}
          </strong>
          . Treat this as directional evidence, not a guaranteed future outcome.
        </p>
        <div className="projection-stack">
          <ProjectionCard title="Current Portfolio (1Y Scenario)" projection={optimization?.projections?.current?.horizon_1y} />
          <ProjectionCard
            title="Optimized Portfolio (1Y Scenario)"
            projection={optimization?.projections?.optimized?.horizon_1y}
          />
        </div>
      </article>

      <div className="panel-grid panel-grid-optimization">
        <article className="surface-card">
          <div className="section-head">
            <h3>Recommended Changes</h3>
            <InfoTip
              label="Recommended changes"
              text="Actions are generated from weight differences. Delta amount appears when original input was in dollar mode."
            />
          </div>
          <div className="holdings-table-wrap">
            <table className="holdings-table">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Action</th>
                  <th>Current Wt</th>
                  <th>Target Wt</th>
                  <th>Delta</th>
                  {optimization?.mode === "amount" ? <th>Delta Amount</th> : null}
                </tr>
              </thead>
              <tbody>
                {(optimization?.recommended_changes || [])
                  .filter((row) => Math.abs(row.delta_weight || 0) >= 0.005)
                  .sort((a, b) => Math.abs(b.delta_weight) - Math.abs(a.delta_weight))
                  .slice(0, 25)
                  .map((row) => (
                    <tr key={`${row.ticker}-${row.action}`}>
                      <td>{row.ticker}</td>
                      <td>
                        <span className={`action-pill action-${row.action}`}>{row.action}</span>
                      </td>
                      <td>{formatPct(row.current_weight)}</td>
                      <td>{formatPct(row.target_weight)}</td>
                      <td>{formatPct(row.delta_weight)}</td>
                      {optimization?.mode === "amount" ? <td>{formatMoney(row.delta_amount)}</td> : null}
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </article>

        <aside className="surface-card side-card">
          <div className="section-head">
            <h3>Top Target Weights</h3>
            <InfoTip
              label="Target weights"
              text="These are the largest recommended positions in the optimized portfolio after all constraints were applied."
            />
          </div>

          <ul className="target-list">
            {(optimization?.optimized_portfolio || []).map((row) => (
              <li key={row.ticker}>
                <div>
                  <strong>{row.ticker}</strong>
                  <span>{row.name || "-"}</span>
                </div>
                <p>{formatPct(row.weight)}</p>
              </li>
            ))}
          </ul>

          <div className="insight-list">
            <h4>Model Insights</h4>
            <ul>
              {(optimization?.insights || []).map((insight) => (
                <li key={insight}>{insight}</li>
              ))}
            </ul>
          </div>
        </aside>
      </div>
    </section>
  );
}
