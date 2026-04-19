export function buildHoldingPayload(mode, rows) {
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

export function mergeWarnings(...lists) {
  return Array.from(
    new Set(
      lists
        .flat()
        .filter((item) => typeof item === "string" && item.trim())
    )
  );
}

export function clampNumber(rawValue, { min, max, fallback }) {
  const numeric = Number(rawValue);
  if (!Number.isFinite(numeric)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, numeric));
}
