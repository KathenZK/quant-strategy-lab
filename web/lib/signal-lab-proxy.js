import { NextResponse } from "next/server";

import { fetchSignalLabResponse } from "./signal-lab-api";

export async function proxySignalLabJson(path, request) {
  const method = request.method || "GET";
  const requestBody = method === "GET" || method === "HEAD" ? undefined : await request.text();
  const { response, body } = await fetchSignalLabResponse(path, {
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

export function createSignalLabRoute(path) {
  return async function GET(request) {
    return proxySignalLabJson(path, request);
  };
}
