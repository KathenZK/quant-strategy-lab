import { STRATEGY_LAB_ENDPOINTS } from "../../../../../lib/strategy-lab-api";
import { proxyStrategyLabJson } from "../../../../../lib/strategy-lab-proxy";

export async function GET(request, { params }) {
  const { job_id: jobId } = await params;
  return proxyStrategyLabJson(STRATEGY_LAB_ENDPOINTS.labJob(jobId), request);
}
