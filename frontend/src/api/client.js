const API_BASE = import.meta.env.VITE_API_BASE || "/api/v1";

async function getJson(path) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${errorText}`);
  }
  return response.json();
}

async function postJson(path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${errorText}`);
  }
  return response.json();
}

export function analyzePortfolio(payload) {
  return postJson("/portfolio/analyze", payload);
}

export function optimizePortfolio(payload) {
  return postJson("/portfolio/optimize", payload);
}

export function fetchTopVolatility(limit = 10) {
  return getJson(`/financials/top-volatility?limit=${limit}`);
}
