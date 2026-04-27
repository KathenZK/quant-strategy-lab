import { NextResponse } from "next/server";

import { fetchStrategyLabResponse } from "./strategy-lab-api";

export async function proxyStrategyLabJson(path, request) {
  const method = request.method || "GET";
  const requestBody = method === "GET" || method === "HEAD" ? undefined : await request.text();
  const { response, body } = await fetchStrategyLabResponse(path, {
    method,
    searchParams: request.nextUrl.searchParams,
    body: requestBody,
  });
  return new NextResponse(body, {
    headers: {
      "cache-control": "no-store",
      "content-type": response.headers.get("content-type") || "application/json; charset=utf-8",
    },
    status: response.status,
  });
}

export function createStrategyLabRoute(path) {
  return async function GET(request) {
    return proxyStrategyLabJson(path, request);
  };
}
