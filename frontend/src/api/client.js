const API_BASE = import.meta.env.VITE_API_BASE || "/api/v1";
const REQUEST_TIMEOUT = 60000; // 60 seconds
const MAX_RETRIES = 2;

class APIError extends Error {
  constructor(status, message, details) {
    super(message);
    this.status = status;
    this.details = details;
    this.name = "APIError";
  }
}

/**
 * Fetch with timeout support
 */
async function fetchWithTimeout(url, options = {}, timeout = REQUEST_TIMEOUT) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);
  
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    });
    clearTimeout(timeoutId);
    return response;
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === "AbortError") {
      throw new APIError(504, "Request timeout - server took too long to respond", null);
    }
    throw error;
  }
}

/**
 * Parse error response from server
 */
async function parseErrorResponse(response) {
  try {
    const data = await response.json();
    return data.detail || data.message || response.statusText;
  } catch {
    const text = await response.text();
    return text || response.statusText;
  }
}

/**
 * Retry logic for transient failures
 */
async function retryableRequest(fn, retries = MAX_RETRIES) {
  for (let i = 0; i <= retries; i++) {
    try {
      return await fn();
    } catch (error) {
      const isTransient = error instanceof APIError && (error.status === 504 || error.status === 503);
      const isLastAttempt = i === retries;
      
      if (!isTransient || isLastAttempt) {
        throw error;
      }
      
      // Wait before retrying (exponential backoff)
      await new Promise(resolve => setTimeout(resolve, Math.pow(2, i) * 1000));
    }
  }
}

async function getJson(path) {
  return retryableRequest(async () => {
    const response = await fetchWithTimeout(`${API_BASE}${path}`);
    if (!response.ok) {
      const detail = await parseErrorResponse(response);
      throw new APIError(response.status, `Failed to fetch ${path}`, detail);
    }
    try {
      return await response.json();
    } catch (error) {
      throw new APIError(500, "Invalid JSON response from server", error.message);
    }
  });
}

async function postJson(path, body) {
  return retryableRequest(async () => {
    const response = await fetchWithTimeout(`${API_BASE}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(body)
    });
    if (!response.ok) {
      const detail = await parseErrorResponse(response);
      throw new APIError(response.status, `Request to ${path} failed`, detail);
    }
    try {
      return await response.json();
    } catch (error) {
      throw new APIError(500, "Invalid JSON response from server", error.message);
    }
  });
}

export function analyzePortfolio(payload) {
  return postJson("/portfolio/analyze", payload);
}

export function optimizePortfolio(payload) {
  return postJson("/portfolio/optimize", payload);
}

export function comparePortfolioHistory(payload) {
  return postJson("/portfolio/compare-history", payload);
}

export function fetchTopVolatility(limit = 10) {
  return getJson(`/financials/top-volatility?limit=${limit}`);
}

export { APIError };
