const DEFAULT_STRATEGY_LAB_API_BASE_URL = "http://127.0.0.1:27098";
const JSON_HEADERS = {
  accept: "application/json",
};

export const STRATEGY_LAB_ENDPOINTS = Object.freeze({
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
  return parseStrategyLabJson(response, body);
}

function parseStrategyLabJson(response, body) {
  if (!response.ok) {
    throw new Error(body || `Strategy Lab API request failed: ${response.status}`);
  }
  return body ? JSON.parse(body) : {};
}

function buildJsonRequestInit(options = {}) {
  const { cache = "no-store", method = "GET", body } = options;
  const requestInit = {
    cache,
    headers: body === undefined ? JSON_HEADERS : { ...JSON_HEADERS, "content-type": "application/json" },
    method,
  };
  if (body !== undefined) {
    requestInit.body = typeof body === "string" ? body : JSON.stringify(body);
  }
  return requestInit;
}

export function strategyLabApiBaseUrl() {
  return (process.env.STRATEGY_LAB_API_BASE_URL || DEFAULT_STRATEGY_LAB_API_BASE_URL).replace(/\/$/, "");
}

export function buildStrategyLabApiUrl(path, searchParams) {
  return appendSearchParams(new URL(path, `${strategyLabApiBaseUrl()}/`), searchParams);
}

export function buildStrategyLabAppUrl(path, searchParams) {
  const url = appendSearchParams(new URL(path, "http://strategy-lab.local/"), searchParams);
  return `${url.pathname}${url.search}`;
}

export async function fetchStrategyLabResponse(path, options = {}) {
  const { searchParams } = options;
  const response = await fetch(buildStrategyLabApiUrl(path, searchParams), {
    ...buildJsonRequestInit(options),
  });
  return { response, body: await response.text() };
}

export async function fetchStrategyLabJson(path, options = {}) {
  const { response, body } = await fetchStrategyLabResponse(path, options);
  return parseStrategyLabJson(response, body);
}

export async function fetchStrategyLabAppJson(path, options = {}) {
  const { searchParams } = options;
  const response = await fetch(buildStrategyLabAppUrl(path, searchParams), {
    ...buildJsonRequestInit(options),
  });
  return readJson(response);
}
