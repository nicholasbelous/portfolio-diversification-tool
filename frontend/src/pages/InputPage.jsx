import { formatMoney, formatNumber } from "../lib/format";
import InfoTip from "../ui/InfoTip";

export default function InputPage({
  mode,
  onChangeMode,
  rows,
  onUpdateRow,
  onAddRow,
  onRemoveRow,
  onAnalyze,
  loading,
  hasEnoughInput,
  validHoldings,
  totalAmount
}) {
  return (
    <section className="page-content">
      <header className="page-header">
        <p className="page-kicker">Step 1</p>
        <h2>Portfolio Setup</h2>
        <p>
          Enter what you currently hold. We use this as the baseline to measure risk, expected return, and possible
          optimization impact.
        </p>
      </header>

      <div className="panel-grid panel-grid-input">
        <article className="surface-card">
          <div className="section-head">
            <h3>Holdings Input</h3>
            <InfoTip
              label="Holdings input"
              text="Use dollar amounts if you know investment size in USD. Use weights if you already have target percentages in decimal form (for example 0.25 = 25%)."
            />
          </div>

          <div className="input-toolbar">
            <div className="mode-toggle">
              <button
                type="button"
                className={mode === "amount" ? "active" : ""}
                onClick={() => onChangeMode("amount")}
              >
                Dollar Amounts
              </button>
              <button
                type="button"
                className={mode === "weight" ? "active" : ""}
                onClick={() => onChangeMode("weight")}
              >
                Weights (0-1)
              </button>
            </div>

            <button type="button" className="ghost-btn" onClick={onAddRow}>
              + Add Holding
            </button>
          </div>

          <div className="holdings-table-wrap">
            <table className="holdings-table">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>{mode === "amount" ? "Amount ($)" : "Weight (0-1)"}</th>
                  <th aria-label="remove" />
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr key={`holding-${index}`}>
                    <td>
                      <input
                        value={row.ticker}
                        onChange={(event) => onUpdateRow(index, "ticker", event.target.value.toUpperCase())}
                        placeholder="AAPL"
                      />
                    </td>
                    <td>
                      <input
                        value={row.value}
                        onChange={(event) => onUpdateRow(index, "value", event.target.value)}
                        placeholder={mode === "amount" ? "5000" : "0.20"}
                      />
                    </td>
                    <td>
                      <button
                        type="button"
                        className="danger-btn"
                        onClick={() => onRemoveRow(index)}
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
            <button type="button" onClick={onAnalyze} disabled={loading || !hasEnoughInput}>
              {loading ? "Running Analysis..." : "Analyze Current Portfolio"}
            </button>
          </div>
        </article>

        <aside className="surface-card side-card">
          <div className="section-head">
            <h3>Input Health Check</h3>
            <InfoTip
              label="Input health"
              text="You need at least two valid holdings to compute diversification and covariance-based metrics."
            />
          </div>

          <div className="checkpoint-list">
            <div>
              <span>Valid Holdings</span>
              <strong>{formatNumber(validHoldings, 0)}</strong>
            </div>
            <div>
              <span>Input Mode</span>
              <strong>{mode === "amount" ? "Dollar Amount" : "Weight"}</strong>
            </div>
            <div>
              <span>Total Value</span>
              <strong>{mode === "amount" ? formatMoney(totalAmount) : "N/A"}</strong>
            </div>
          </div>

          <div className="note-card">
            <h4>What happens next?</h4>
            <p>
              We calculate risk and return metrics from historical data, then suggest a low-turnover optimization plan
              with realistic tradeoffs.
            </p>
          </div>
        </aside>
      </div>
    </section>
  );
}
