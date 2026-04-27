import { STRATEGY_LAB_ENDPOINTS } from "../../../../lib/strategy-lab-api";
import { proxyStrategyLabJson } from "../../../../lib/strategy-lab-proxy";

export async function POST(request) {
  return proxyStrategyLabJson(STRATEGY_LAB_ENDPOINTS.labBacktests, request);
}
