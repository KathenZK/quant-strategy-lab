const DEFAULT_SIGNAL_LAB_API_BASE_URL = "http://127.0.0.1:8000";
const JSON_HEADERS = {
  accept: "application/json",
};

export const SIGNAL_LAB_ENDPOINTS = Object.freeze({
  health: "/api/health",
  runs: "/api/runs",
  runDetail: "/api/run-detail",
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
  const { searchParams, cache = "no-store" } = options;
  const response = await fetch(buildSignalLabApiUrl(path, searchParams), {
    cache,
    headers: JSON_HEADERS,
  });
  return { response, body: await response.text() };
}

export async function fetchSignalLabJson(path, options = {}) {
  const { searchParams, cache = "no-store" } = options;
  const response = await fetch(buildSignalLabApiUrl(path, searchParams), {
    cache,
    headers: JSON_HEADERS,
  });
  return readJson(response);
}

export async function fetchSignalLabAppJson(path, options = {}) {
  const { searchParams, cache = "no-store" } = options;
  const response = await fetch(buildSignalLabAppUrl(path, searchParams), {
    cache,
    headers: JSON_HEADERS,
  });
  return readJson(response);
}
