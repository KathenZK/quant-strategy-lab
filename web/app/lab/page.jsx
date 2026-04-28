import StrategyLabClient from "../../components/lab/strategy-lab-client";
import { fetchStrategyLabJson, STRATEGY_LAB_ENDPOINTS } from "../../lib/strategy-lab-api";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "策略实验室",
  description: "创建策略实验、选择数据源和数据快照，并触发回测任务。",
};

export default async function LabPage() {
  let templates = [];
  let runs = [];
  try {
    const payload = await fetchStrategyLabJson(STRATEGY_LAB_ENDPOINTS.strategyTemplates);
    templates = payload.templates ?? [];
  } catch {
    templates = [];
  }

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

  return <StrategyLabClient initialTemplates={templates} initialRuns={runs} />;
}
