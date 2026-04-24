import { NextResponse } from "next/server";

import { fetchSignalLabResponse } from "./signal-lab-api";

export async function proxySignalLabJson(path, request) {
  const { response, body } = await fetchSignalLabResponse(path, {
    searchParams: request.nextUrl.searchParams,
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
