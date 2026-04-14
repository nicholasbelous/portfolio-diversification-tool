import { useEffect, useState } from "react";

import { fetchHistory, fetchSnapshot, fetchTopVolatility } from "./api/client";
import PriceChart from "./components/PriceChart";
import SnapshotGrid from "./components/SnapshotGrid";
import TopVolatilityList from "./components/TopVolatilityList";

function normalizeHistoryPayload(payload) {
  const items = Array.isArray(payload?.items) ? payload.items : [];
  return items
    .map((item) => ({
      date: item.trading_date,
      close: Number(item.close)
    }))
    .filter((item) => Number.isFinite(item.close));
}

export default function App() {
  const [tickerInput, setTickerInput] = useState("AAPL");
  const [activeTicker, setActiveTicker] = useState("AAPL");
  const [range, setRange] = useState("1y");
  const [snapshot, setSnapshot] = useState(null);
  const [historyPoints, setHistoryPoints] = useState([]);
  const [topVolatility, setTopVolatility] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const canSearch = tickerInput.trim().length > 0;

  async function loadTickerData(ticker) {
    const symbol = ticker.trim().toUpperCase();
    if (!symbol) {
      return;
    }

    setLoading(true);
    setError("");

    try {
      const [snapshotData, historyData, topVolatilityData] = await Promise.all([
        fetchSnapshot(symbol),
        fetchHistory(symbol),
        fetchTopVolatility(10)
      ]);

      setActiveTicker(symbol);
      setSnapshot(snapshotData);
      setHistoryPoints(normalizeHistoryPayload(historyData));
      setTopVolatility(Array.isArray(topVolatilityData.items) ? topVolatilityData.items : []);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    void loadTickerData(tickerInput);
  }

  useEffect(() => {
    void loadTickerData("AAPL");
  }, []);

  return (
    <main className="app-shell">
      <div className="bg-shape bg-shape-a" />
      <div className="bg-shape bg-shape-b" />
      <header className="hero">
        <p className="eyebrow">Portfolio Diversification Tool</p>
        <h1>Market Insight Dashboard</h1>
        <p>
          Search any loaded ticker to view risk metrics, current snapshot, and historical close prices.
        </p>
        <form className="ticker-form" onSubmit={handleSubmit}>
          <label htmlFor="ticker-input">Ticker</label>
          <input
            id="ticker-input"
            value={tickerInput}
            onChange={(event) => setTickerInput(event.target.value.toUpperCase())}
            placeholder="AAPL"
          />
          <button type="submit" disabled={!canSearch || loading}>
            {loading ? "Loading..." : "Load Data"}
          </button>
        </form>
      </header>

      {error ? (
        <section className="panel error-panel">
          <h2>Request Error</h2>
          <p>{error}</p>
        </section>
      ) : null}

      <section className="content-grid">
        <div className="main-column">
          <SnapshotGrid snapshot={snapshot} />
          <PriceChart
            ticker={activeTicker}
            rawPoints={historyPoints}
            range={range}
            onRangeChange={setRange}
          />
        </div>
        <aside className="side-column">
          <TopVolatilityList rows={topVolatility} />
        </aside>
      </section>
    </main>
  );
}
