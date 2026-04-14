export default function TopVolatilityList({ rows }) {
  return (
    <section className="panel">
      <header className="panel-header">
        <h2>Most Volatile</h2>
      </header>
      <ul className="volatility-list">
        {rows.map((row) => (
          <li key={row.ticker}>
            <div>
              <strong>{row.ticker}</strong>
              <span>{row.name}</span>
            </div>
            <p>{row.volatility_1y == null ? "-" : `${(row.volatility_1y * 100).toFixed(2)}%`}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
