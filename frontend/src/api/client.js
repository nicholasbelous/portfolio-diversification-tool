const API_BASE = import.meta.env.VITE_API_BASE || "/api/v1";

async function getJson(path) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${errorText}`);
  }
  return response.json();
}

export function fetchSnapshot(ticker) {
  return getJson(`/financials/${ticker}`);
}

export function fetchHistory(ticker) {
  return getJson(`/financials/${ticker}/history?limit=2000`);
}

export function fetchTopVolatility(limit = 10) {
  return getJson(`/financials/top-volatility?limit=${limit}`);
}
