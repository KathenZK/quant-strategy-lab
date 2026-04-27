import DashboardClient from "../../components/dashboard-client";
import { fetchStrategyLabJson, STRATEGY_LAB_ENDPOINTS } from "../../lib/strategy-lab-api";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "回测记录",
  description: "查看策略排行、实验批次、权益曲线与运行指纹。",
};

export default async function BacktestsPage() {
  let initialRuns = [];
  let initialError = "";

  try {
    const payload = await fetchStrategyLabJson(STRATEGY_LAB_ENDPOINTS.runs);
    initialRuns = payload.runs ?? [];
  } catch (error) {
    initialError = error instanceof Error ? error.message : "Failed to load runs.";
  }

  return <DashboardClient initialRuns={initialRuns} initialError={initialError} />;
}
