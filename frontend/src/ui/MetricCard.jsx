import InfoTip from "./InfoTip";

export default function MetricCard({ label, value, tooltip, note, tone = "neutral" }) {
  return (
    <article className={`metric-card tone-${tone}`}>
      <header className="metric-head">
        <h3>{label}</h3>
        {tooltip ? <InfoTip label={label} text={tooltip} /> : null}
      </header>
      <p>{value}</p>
      {note ? <small>{note}</small> : null}
    </article>
  );
}
