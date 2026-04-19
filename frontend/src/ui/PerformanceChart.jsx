import { useMemo } from "react";

import { buildComparisonChart, CHART_RANGES } from "../lib/chart";
import { formatDate, formatPct } from "../lib/format";

export default function PerformanceChart({ historyCompare, chartRange, onChangeRange }) {
  const chart = useMemo(
    () => buildComparisonChart(historyCompare, chartRange),
    [historyCompare, chartRange]
  );

  if (!historyCompare) {
    return (
      <article className="chart-card">
        <header className="chart-card-head">
          <h3>Historical Performance View</h3>
        </header>
        <p className="muted">Run optimization to load the current vs optimized chart.</p>
      </article>
    );
  }

  return (
    <article className="chart-card">
      <header className="chart-card-head">
        <div>
          <h3>Color-Coded Growth Comparison</h3>
          <p className="muted">
            Growth of $1 using historical daily returns. This is a scenario check, not a guaranteed forecast.
          </p>
        </div>
        <div className="range-toggle">
          {CHART_RANGES.map((range) => (
            <button
              key={range.key}
              type="button"
              className={chartRange === range.key ? "active" : ""}
              onClick={() => onChangeRange(range.key)}
            >
              {range.key}
            </button>
          ))}
        </div>
      </header>

      {chart ? (
        <>
          <div className="chart-wrap">
            <svg viewBox={`0 0 ${chart.width} ${chart.height}`} role="img" aria-label="Portfolio comparison chart">
              {chart.yTicks.map((tick) => (
                <g key={`y-${tick.label}`}>
                  <line
                    x1={chart.padding.left}
                    x2={chart.width - chart.padding.right}
                    y1={tick.y}
                    y2={tick.y}
                    className="chart-grid-line"
                  />
                  <text x={10} y={tick.y + 4} className="chart-axis-label">
                    {tick.label}
                  </text>
                </g>
              ))}

              {chart.xTicks.map((tick) => (
                <text key={`x-${tick.label}`} x={tick.x} y={chart.height - 12} className="chart-axis-label x-axis">
                  {tick.label}
                </text>
              ))}

              {chart.lines.map((line) => (
                <polyline
                  key={line.key}
                  className="chart-line"
                  points={line.polyline}
                  stroke={line.color}
                  strokeWidth="3"
                />
              ))}
            </svg>
          </div>

          <div className="chart-legend">
            {chart.lines.map((line) => (
              <span key={line.key}>
                <i style={{ backgroundColor: line.color }} />
                {line.label}: {formatPct((line.lastValue || 1) - 1)}
              </span>
            ))}
          </div>

          <div className="chart-foot">
            <span>
              {formatDate(chart.startDate)} to {formatDate(chart.endDate)}
            </span>
            <span>{historyCompare.window_days || 0} trading days</span>
          </div>
        </>
      ) : (
        <p className="muted">Not enough overlapping history to render a reliable chart.</p>
      )}
    </article>
  );
}
