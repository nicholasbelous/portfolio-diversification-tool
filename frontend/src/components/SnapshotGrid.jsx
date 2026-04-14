function formatPercent(value) {
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

export default function SnapshotGrid({ snapshot }) {
  if (!snapshot) {
    return null;
  }

  const metrics = [
    { label: "Beta", value: formatNumber(snapshot.beta) },
    { label: "Volatility (1Y)", value: formatPercent(snapshot.volatility_1y) },
    { label: "Return (1M)", value: formatPercent(snapshot.return_1m) },
    { label: "Return (3M)", value: formatPercent(snapshot.return_3m) },
    { label: "Return (1Y)", value: formatPercent(snapshot.return_1y) },
    { label: "Market Cap", value: formatMoney(snapshot.market_cap) },
    { label: "P/E", value: formatNumber(snapshot.trailing_pe) },
    { label: "P/B", value: formatNumber(snapshot.price_to_book) },
    { label: "Debt/Equity", value: formatNumber(snapshot.debt_to_equity) },
    { label: "Profit Margin", value: formatPercent(snapshot.profit_margin) }
  ];

  return (
    <section className="panel">
      <header className="panel-header">
        <h2>
          {snapshot.ticker} Overview
          <span className="subheading">
            {snapshot.name} · {snapshot.sector}
          </span>
        </h2>
      </header>
      <div className="metric-grid">
        {metrics.map((metric) => (
          <article key={metric.label} className="metric-card">
            <h3>{metric.label}</h3>
            <p>{metric.value}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
