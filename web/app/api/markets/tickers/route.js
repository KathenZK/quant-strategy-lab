import { STRATEGY_LAB_ENDPOINTS } from "../../../../lib/strategy-lab-api";
import { createStrategyLabRoute } from "../../../../lib/strategy-lab-proxy";

export const GET = createStrategyLabRoute(STRATEGY_LAB_ENDPOINTS.marketTickers);
