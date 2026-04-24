const DEFAULT_SIGNAL_LAB_API_BASE_URL = "http://127.0.0.1:8000";

export function signalLabApiBaseUrl() {
  return (process.env.SIGNAL_LAB_API_BASE_URL || DEFAULT_SIGNAL_LAB_API_BASE_URL).replace(/\/$/, "");
}

export function buildSignalLabApiUrl(path, searchParams) {
  const url = new URL(path, `${signalLabApiBaseUrl()}/`);
  if (searchParams) {
    for (const [key, value] of searchParams.entries()) {
      url.searchParams.append(key, value);
    }
  }
  return url;
}

export async function fetchSignalLabJson(path, options = {}) {
  const { searchParams, cache = "no-store" } = options;
  const response = await fetch(buildSignalLabApiUrl(path, searchParams), {
    cache,
    headers: {
      accept: "application/json",
    },
  });
  const body = await response.text();
  if (!response.ok) {
    throw new Error(body || `Signal Lab API request failed: ${response.status}`);
  }
  return body ? JSON.parse(body) : {};
}
