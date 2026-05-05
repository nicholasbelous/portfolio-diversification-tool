import InfoTip from "./InfoTip";
import { formatPct } from "../lib/format";

export default function ProjectionCard({ title, projection }) {
  const historical = projection?.historical;
  const monteCarlo = projection?.monte_carlo;
  const mlForecast = projection?.ml_forecast;
  const mlQuality = mlForecast?.improvement_vs_naive_pct;
  const qualityLabel =
    mlQuality == null
      ? "ML quality unavailable"
      : mlQuality >= 0
        ? `ML MAE vs naive: ${formatPct(mlQuality)} better`
        : `ML MAE vs naive: ${formatPct(Math.abs(mlQuality))} worse`;

  return (
    <article className="projection-card">
      <header>
        <h4>{title}</h4>
        <InfoTip
          label={`${title} projection`}
          text="Historical uses rolling windows from observed returns. Monte Carlo uses simulated return paths with distribution assumptions. ML forecast uses an autoregressive model trained on recent return patterns."
        />
      </header>
      <div className="projection-grid">
        <div>
          <p className="projection-label">Historical p10 / p50 / p90</p>
          <p>
            {historical
              ? `${formatPct(historical.p10)} / ${formatPct(historical.p50)} / ${formatPct(historical.p90)}`
              : "-"}
          </p>
        </div>
        <div>
          <p className="projection-label">Monte Carlo p10 / p50 / p90</p>
          <p>
            {monteCarlo
              ? `${formatPct(monteCarlo.p10)} / ${formatPct(monteCarlo.p50)} / ${formatPct(monteCarlo.p90)}`
              : "-"}
          </p>
        </div>
        <div>
          <p className="projection-label">ML Forecast p10 / p50 / p90</p>
          <p>
            {mlForecast
              ? `${formatPct(mlForecast.p10)} / ${formatPct(mlForecast.p50)} / ${formatPct(mlForecast.p90)}`
              : "-"}
          </p>
          <small>{qualityLabel}</small>
        </div>
      </div>
    </article>
  );
}
