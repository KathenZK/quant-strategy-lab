import { SIGNAL_LAB_ENDPOINTS } from "../../../lib/signal-lab-api";
import { createSignalLabRoute } from "../../../lib/signal-lab-proxy";

export const GET = createSignalLabRoute(SIGNAL_LAB_ENDPOINTS.health);
