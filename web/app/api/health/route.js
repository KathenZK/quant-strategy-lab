import { proxySignalLabJson } from "../../../lib/signal-lab-proxy";

export async function GET(request) {
  return proxySignalLabJson("/api/health", request);
}
