import { useMemo, useState } from "react";

import { analyzePortfolio, fetchTopVolatility, optimizePortfolio } from "./api/client";

function formatPct(value) {
  if (value == null || Number.isNaN(value)) {
    return "-";
  }
  return `${(value * 100).toFixed(2)}%`;
}

function formatNumber(value) {
  if (value == null || Number.isNaN(value)) {
    return "-";
  }
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2
  }).format(value);
}

function formatMoney(value) {
  if (value == null || Number.isNaN(value)) {
    return "-";
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0
  }).format(value);
}

function buildHoldingPayload(mode, rows) {
  return rows
    .map((row) => {
      const ticker = row.ticker.trim().toUpperCase();
      const numeric = Number(row.value);
      if (!ticker || !Number.isFinite(numeric) || numeric <= 0) {
        return null;
      }
      if (mode === "amount") {
        return { ticker, amount: numeric };
      }
      return { ticker, weight: numeric };
    })
    .filter(Boolean);
}

function StepPill({ index, active, title }) {
  return (
    <div className={`step-pill ${active ? "active" : ""}`}>
      <span>{index}</span>
      <p>{title}</p>
    </div>
  );
}

function MetricCard({ label, value, hint }) {
  return (
    <article className="metric-card">
      <h3>{label}</h3>
      <p>{value}</p>
      {hint ? <small>{hint}</small> : null}
    </article>
  );
}

function ProjectionCard({ title, projection }) {
  const hist = projection?.historical;
  const mc = projection?.monte_carlo;
  return (
    <article className="projection-card">
      <h4>{title}</h4>
      <div className="projection-grid">
        <div>
          <p className="projection-label">Historical p10 / p50 / p90</p>
          <p>{hist ? `${formatPct(hist.p10)} / ${formatPct(hist.p50)} / ${formatPct(hist.p90)}` : "-"}</p>
        </div>
        <div>
          <p className="projection-label">Monte Carlo p10 / p50 / p90</p>
          <p>{mc ? `${formatPct(mc.p10)} / ${formatPct(mc.p50)} / ${formatPct(mc.p90)}` : "-"}</p>
        </div>
      </div>
    </article>
  );
}

export default function App() {
  const [mode, setMode] = useState("amount");
  const [rows, setRows] = useState([
    { ticker: "AAPL", value: "7000" },
    { ticker: "MSFT", value: "5000" },
    { ticker: "NVDA", value: "3000" },
    { ticker: "JPM", value: "2500" }
  ]);
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [warnings, setWarnings] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [optimization, setOptimization] = useState(null);
  const [maxChanges, setMaxChanges] = useState(5);
  const [tradeCostRate, setTradeCostRate] = useState(0.0015);
  const [topVolatility, setTopVolatility] = useState([]);

  const holdingPayload = useMemo(() => buildHoldingPayload(mode, rows), [mode, rows]);
  const hasEnoughInput = holdingPayload.length >= 2;

  async function loadTopVolatility() {
    try {
      const data = await fetchTopVolatility(8);
      setTopVolatility(Array.isArray(data.items) ? data.items : []);
    } catch {
      setTopVolatility([]);
    }
  }

  async function handleAnalyze() {
    if (!hasEnoughInput) {
      setError("Add at least two valid holdings before analyzing.");
      return;
    }
    setLoading(true);
    setError("");
    setWarnings([]);
    try {
      const response = await analyzePortfolio({ holdings: holdingPayload });
      setAnalysis(response.data);
      setWarnings(response.data?.warnings || []);
      setStep(1);
      if (!topVolatility.length) {
        void loadTopVolatility();
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Analysis request failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleOptimize() {
    if (!hasEnoughInput) {
      setError("Add at least two valid holdings before optimizing.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const response = await optimizePortfolio({
        holdings: holdingPayload,
        max_changes: Number(maxChanges),
        transaction_cost_rate: Number(tradeCostRate),
        include_sp500_additions: true,
        include_etfs: true
      });
      setOptimization(response.data);
      setWarnings(response.data?.warnings || []);
      setStep(2);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Optimization request failed.");
    } finally {
      setLoading(false);
    }
  }

  function updateRow(index, key, value) {
    setRows((prev) => prev.map((row, i) => (i === index ? { ...row, [key]: value } : row)));
  }

  function addRow() {
    setRows((prev) => [...prev, { ticker: "", value: "" }]);
  }

  function removeRow(index) {
    setRows((prev) => prev.filter((_, i) => i !== index));
  }

  return (
    <main className="app-shell">
      <div className="bg-shape bg-shape-a" />
      <div className="bg-shape bg-shape-b" />

      <header className="hero">
        <p className="eyebrow">Portfolio Diversification Tool</p>
        <h1>Portfolio Risk & Optimization Workshop</h1>
        <p>
          Input your current portfolio, evaluate current risk/return profile, then generate a low-turnover optimized
          portfolio with projected impact.
        </p>
      </header>

      <section className="panel">
        <div className="step-row">
          <StepPill index="1" title="Input" active={step === 0} />
          <StepPill index="2" title="Analysis" active={step === 1} />
          <StepPill index="3" title="Optimization" active={step === 2} />
        </div>
      </section>

      <section className="panel">
        <header className="panel-header">
          <h2>Step 1: Portfolio Input</h2>
        </header>

        <div className="input-toolbar">
          <div className="mode-toggle">
            <button
              type="button"
              className={mode === "amount" ? "active" : ""}
              onClick={() => setMode("amount")}
            >
              Dollar Amounts
            </button>
            <button
              type="button"
              className={mode === "weight" ? "active" : ""}
              onClick={() => setMode("weight")}
            >
              Weights (0-1)
            </button>
          </div>

          <button type="button" className="ghost-btn" onClick={addRow}>
            + Add Holding
          </button>
        </div>

        <div className="holdings-table-wrap">
          <table className="holdings-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>{mode === "amount" ? "Amount ($)" : "Weight (0-1)"}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={`holding-${index}`}>
                  <td>
                    <input
                      value={row.ticker}
                      onChange={(event) => updateRow(index, "ticker", event.target.value.toUpperCase())}
                      placeholder="AAPL"
                    />
                  </td>
                  <td>
                    <input
                      value={row.value}
                      onChange={(event) => updateRow(index, "value", event.target.value)}
                      placeholder={mode === "amount" ? "5000" : "0.20"}
                    />
                  </td>
                  <td>
                    <button
                      type="button"
                      className="danger-btn"
                      onClick={() => removeRow(index)}
                      disabled={rows.length <= 2}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="action-row">
          <button type="button" onClick={handleAnalyze} disabled={loading || !hasEnoughInput}>
            {loading ? "Analyzing..." : "Run Analysis"}
          </button>
        </div>
      </section>

      {error ? (
        <section className="panel error-panel">
          <h2>Request Error</h2>
          <p>{error}</p>
        </section>
      ) : null}

      {warnings.length ? (
        <section className="panel warning-panel">
          <h2>Warnings</h2>
          <ul>
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {analysis ? (
        <section className="panel">
          <header className="panel-header">
            <h2>Step 2: Current Portfolio Analysis</h2>
          </header>
          <div className="metric-grid">
            <MetricCard label="Expected Annual Return" value={formatPct(analysis.metrics?.expected_return_annual)} />
            <MetricCard label="Annual Volatility" value={formatPct(analysis.metrics?.volatility_annual)} />
            <MetricCard label="Sharpe Ratio" value={formatNumber(analysis.metrics?.sharpe_ratio)} />
            <MetricCard label="Weighted Beta" value={formatNumber(analysis.metrics?.beta_weighted)} />
            <MetricCard label="Max Drawdown (1Y)" value={formatPct(analysis.metrics?.max_drawdown_1y)} />
            <MetricCard label="Holdings Count" value={formatNumber(analysis.holdings?.length || 0)} />
          </div>

          <div className="projection-stack">
            <ProjectionCard title="3 Month Projection" projection={analysis.projections?.horizon_3m} />
            <ProjectionCard title="1 Year Projection" projection={analysis.projections?.horizon_1y} />
          </div>

          <div className="action-row dual">
            <div className="optimizer-controls">
              <label>
                Max Changes
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={maxChanges}
                  onChange={(event) => setMaxChanges(event.target.value)}
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
                  onChange={(event) => setTradeCostRate(event.target.value)}
                />
              </label>
            </div>
            <button type="button" onClick={handleOptimize} disabled={loading}>
              {loading ? "Optimizing..." : "Run Optimization"}
            </button>
          </div>
        </section>
      ) : null}

      {optimization ? (
        <section className="panel">
          <header className="panel-header">
            <h2>Step 3: Optimized Portfolio & Recommended Changes</h2>
          </header>

          <div className="compare-grid">
            <MetricCard
              label="Current Return (Annual)"
              value={formatPct(optimization.current_metrics?.expected_return_annual)}
            />
            <MetricCard
              label="Optimized Return (Annual)"
              value={formatPct(optimization.optimized_metrics?.expected_return_annual)}
            />
            <MetricCard
              label="Current Volatility"
              value={formatPct(optimization.current_metrics?.volatility_annual)}
            />
            <MetricCard
              label="Optimized Volatility"
              value={formatPct(optimization.optimized_metrics?.volatility_annual)}
            />
            <MetricCard label="Sharpe Change" value={formatNumber(optimization.impact?.sharpe_delta)} />
            <MetricCard label="Turnover" value={formatPct(optimization.impact?.turnover)} />
            <MetricCard
              label="Estimated Trade Cost"
              value={formatPct(optimization.impact?.estimated_trade_cost)}
            />
            <MetricCard label="Max Ticker Changes" value={formatNumber(optimization.settings?.max_changes)} />
          </div>

          <div className="projection-stack">
            <ProjectionCard
              title="Current Portfolio Projection (1Y)"
              projection={optimization.projections?.current?.horizon_1y}
            />
            <ProjectionCard
              title="Optimized Portfolio Projection (1Y)"
              projection={optimization.projections?.optimized?.horizon_1y}
            />
          </div>

          <div className="table-block">
            <h3>Recommended Changes</h3>
            <table className="holdings-table">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Action</th>
                  <th>Current Wt</th>
                  <th>Target Wt</th>
                  <th>Delta</th>
                  {optimization.mode === "amount" ? <th>Delta Amount</th> : null}
                </tr>
              </thead>
              <tbody>
                {(optimization.recommended_changes || [])
                  .filter((row) => Math.abs(row.delta_weight || 0) >= 0.005)
                  .sort((a, b) => Math.abs(b.delta_weight) - Math.abs(a.delta_weight))
                  .slice(0, 20)
                  .map((row) => (
                    <tr key={`${row.ticker}-${row.action}`}>
                      <td>{row.ticker}</td>
                      <td>{row.action}</td>
                      <td>{formatPct(row.current_weight)}</td>
                      <td>{formatPct(row.target_weight)}</td>
                      <td>{formatPct(row.delta_weight)}</td>
                      {optimization.mode === "amount" ? <td>{formatMoney(row.delta_amount)}</td> : null}
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>

          <div className="table-block">
            <h3>Optimized Target Weights</h3>
            <table className="holdings-table">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Name</th>
                  <th>Target Weight</th>
                </tr>
              </thead>
              <tbody>
                {(optimization.optimized_portfolio || []).map((row) => (
                  <tr key={row.ticker}>
                    <td>{row.ticker}</td>
                    <td>{row.name || "-"}</td>
                    <td>{formatPct(row.weight)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="insight-list">
            <h3>Optimization Insights</h3>
            <ul>
              {(optimization.insights || []).map((insight) => (
                <li key={insight}>{insight}</li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}

      {topVolatility.length ? (
        <section className="panel">
          <header className="panel-header">
            <h2>High-Volatility Universe Sample</h2>
          </header>
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
        </section>
      ) : null}
    </main>
  );
}
