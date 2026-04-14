function formatCurrency(value) {
  if (value == null || Number.isNaN(value)) {
    return "-";
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2
  }).format(value);
}

function buildPath(points, width, height, padding) {
  if (points.length < 2) {
    return "";
  }

  const xs = points.map((_, index) => index);
  const ys = points.map((p) => p.close);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);

  const xSpan = maxX - minX || 1;
  const ySpan = maxY - minY || 1;
  const innerW = width - padding * 2;
  const innerH = height - padding * 2;

  const normalized = points.map((point, index) => {
    const x = padding + ((index - minX) / xSpan) * innerW;
    const y = padding + innerH - ((point.close - minY) / ySpan) * innerH;
    return { x, y };
  });

  return normalized
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(" ");
}

function clampRange(points, range) {
  if (range === "all") {
    return points;
  }
  if (range === "3m") {
    return points.slice(-63);
  }
  return points.slice(-252);
}

export default function PriceChart({ ticker, rawPoints, range, onRangeChange }) {
  const points = clampRange(rawPoints, range);
  const width = 920;
  const height = 320;
  const padding = 28;

  if (!points.length) {
    return (
      <section className="panel chart-panel">
        <header className="panel-header">
          <h2>Price History</h2>
        </header>
        <p className="muted">No history available for this ticker.</p>
      </section>
    );
  }

  const first = points[0].close;
  const last = points[points.length - 1].close;
  const changePct = first ? ((last - first) / first) * 100 : 0;
  const isPositive = changePct >= 0;
  const pathData = buildPath(points, width, height, padding);

  return (
    <section className="panel chart-panel">
      <header className="panel-header chart-header">
        <div>
          <h2>{ticker} Price History</h2>
          <p className={`change ${isPositive ? "positive" : "negative"}`}>
            {isPositive ? "+" : ""}
            {changePct.toFixed(2)}% ({range.toUpperCase()})
          </p>
        </div>
        <div className="range-toggle">
          {[
            { key: "3m", label: "3M" },
            { key: "1y", label: "1Y" },
            { key: "all", label: "ALL" }
          ].map((option) => (
            <button
              key={option.key}
              type="button"
              className={range === option.key ? "active" : ""}
              onClick={() => onRangeChange(option.key)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </header>

      <div className="chart-wrap">
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${ticker} close price line chart`}>
          <defs>
            <linearGradient id="lineFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgba(15, 105, 240, 0.35)" />
              <stop offset="100%" stopColor="rgba(15, 105, 240, 0)" />
            </linearGradient>
          </defs>
          <path d={pathData} className="chart-line" />
        </svg>
      </div>

      <div className="chart-foot">
        <span>Start: {formatCurrency(first)}</span>
        <span>Latest: {formatCurrency(last)}</span>
        <span>Points: {points.length}</span>
      </div>
    </section>
  );
}
