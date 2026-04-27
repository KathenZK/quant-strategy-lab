const DEFAULT_SIGNAL_LAB_API_BASE_URL = "http://127.0.0.1:27098";
const JSON_HEADERS = {
  accept: "application/json",
};

export const SIGNAL_LAB_ENDPOINTS = Object.freeze({
  health: "/api/health",
  runs: "/api/runs",
  runDetail: "/api/run-detail",
  experimentDetail: "/api/experiment-detail",
  comparisonDetail: "/api/comparison-detail",
  marketSources: "/api/markets/sources",
  marketInstruments: "/api/markets/instruments",
  marketTickers: "/api/markets/tickers",
  marketOhlcv: "/api/markets/ohlcv",
  strategyTemplates: "/api/lab/strategy-templates",
  labBacktests: "/api/lab/backtests",
  labJob: (jobId) => `/api/lab/jobs/${encodeURIComponent(jobId)}`,
  newsEvents: "/api/news/events",
});

function normalizeSearchParams(searchParams) {
  if (!searchParams) {
    return null;
  }
  return searchParams instanceof URLSearchParams ? searchParams : new URLSearchParams(searchParams);
}

function appendSearchParams(url, searchParams) {
  const normalized = normalizeSearchParams(searchParams);
  if (!normalized) {
    return url;
  }
  for (const [key, value] of normalized.entries()) {
    url.searchParams.append(key, value);
  }
  return url;
}

async function readJson(response) {
  const body = await response.text();
  if (!response.ok) {
    throw new Error(body || `Signal Lab API request failed: ${response.status}`);
  }
  return body ? JSON.parse(body) : {};
}

export function signalLabApiBaseUrl() {
  return (process.env.SIGNAL_LAB_API_BASE_URL || DEFAULT_SIGNAL_LAB_API_BASE_URL).replace(/\/$/, "");
}

export function buildSignalLabApiUrl(path, searchParams) {
  return appendSearchParams(new URL(path, `${signalLabApiBaseUrl()}/`), searchParams);
}

export function buildSignalLabAppUrl(path, searchParams) {
  const url = appendSearchParams(new URL(path, "http://signal-lab.local/"), searchParams);
  return `${url.pathname}${url.search}`;
}

export async function fetchSignalLabResponse(path, options = {}) {
  const { searchParams, cache = "no-store", method = "GET", body } = options;
  const requestInit = {
    cache,
    headers: body === undefined ? JSON_HEADERS : { ...JSON_HEADERS, "content-type": "application/json" },
    method,
  };
  if (body !== undefined) {
    requestInit.body = typeof body === "string" ? body : JSON.stringify(body);
  }
  const response = await fetch(buildSignalLabApiUrl(path, searchParams), {
    ...requestInit,
  });
  return { response, body: await response.text() };
}

export async function fetchSignalLabJson(path, options = {}) {
  const { response, body } = await fetchSignalLabResponse(path, options);
  if (!response.ok) {
    throw new Error(body || `Signal Lab API request failed: ${response.status}`);
  }
  return body ? JSON.parse(body) : {};
}

export async function fetchSignalLabAppJson(path, options = {}) {
  const { searchParams, cache = "no-store", method = "GET", body } = options;
  const requestInit = {
    cache,
    headers: body === undefined ? JSON_HEADERS : { ...JSON_HEADERS, "content-type": "application/json" },
    method,
  };
  if (body !== undefined) {
    requestInit.body = typeof body === "string" ? body : JSON.stringify(body);
  }
  const response = await fetch(buildSignalLabAppUrl(path, searchParams), {
    ...requestInit,
  });
  return readJson(response);
}
