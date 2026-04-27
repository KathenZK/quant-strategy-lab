import { SIGNAL_LAB_ENDPOINTS } from "../../../../../lib/signal-lab-api";
import { proxySignalLabJson } from "../../../../../lib/signal-lab-proxy";

export async function GET(request, { params }) {
  const { job_id: jobId } = await params;
  return proxySignalLabJson(SIGNAL_LAB_ENDPOINTS.labJob(jobId), request);
}
