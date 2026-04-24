import { NextResponse } from "next/server";

import { buildSignalLabApiUrl } from "./signal-lab-api";

export async function proxySignalLabJson(path, request) {
  const response = await fetch(buildSignalLabApiUrl(path, request.nextUrl.searchParams), {
    cache: "no-store",
    headers: {
      accept: "application/json",
    },
  });
  const body = await response.text();
  return new NextResponse(body, {
    headers: {
      "cache-control": "no-store",
      "content-type": response.headers.get("content-type") || "application/json; charset=utf-8",
    },
    status: response.status,
  });
}
