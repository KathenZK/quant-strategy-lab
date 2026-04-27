import { SIGNAL_LAB_ENDPOINTS } from "../../../../lib/signal-lab-api";
import { proxySignalLabJson } from "../../../../lib/signal-lab-proxy";

export async function POST(request) {
  return proxySignalLabJson(SIGNAL_LAB_ENDPOINTS.labBacktests, request);
}
