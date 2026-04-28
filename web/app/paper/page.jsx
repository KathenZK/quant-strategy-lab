import PaperClient from "../../components/paper-client";
import { fetchStrategyLabJson, STRATEGY_LAB_ENDPOINTS } from "../../lib/strategy-lab-api";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "模拟盘",
  description: "查看策略候选、模拟盘摘要和已产出的 paper trading 报告。",
};

export default async function PaperPage() {
  let runs = [];

  try {
    const searchParams = new URLSearchParams({
      kind: "workflow_run",
      limit: "200",
      sort_by: "generated_at",
      sort_order: "desc",
    });
    const payload = await fetchStrategyLabJson(STRATEGY_LAB_ENDPOINTS.runs, { searchParams });
    runs = payload.runs ?? [];
  } catch {
    runs = [];
  }

  return <PaperClient initialRuns={runs} />;
}
