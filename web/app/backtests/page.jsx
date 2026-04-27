import { fetchStrategyLabJson, STRATEGY_LAB_ENDPOINTS } from "../../lib/strategy-lab-api";
import BacktestsClient from "../../components/backtests-client";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "回测记录",
  description: "查看策略回测批次、核心指标与运行指纹。",
};

const BACKTEST_PAGE_SIZE = 30;

export default async function BacktestsPage() {
  let runs = [];
  let initialError = "";

  try {
    const searchParams = new URLSearchParams({
      kind: "workflow_run",
      limit: String(BACKTEST_PAGE_SIZE + 1),
      sort_by: "generated_at",
      sort_order: "desc",
    });
    const payload = await fetchStrategyLabJson(STRATEGY_LAB_ENDPOINTS.runs, { searchParams });
    runs = payload.runs ?? [];
  } catch (error) {
    initialError = error instanceof Error ? error.message : "Failed to load runs.";
  }

  const recordsForDisplay = runs.slice(0, BACKTEST_PAGE_SIZE);
  const hasMore = runs.length > BACKTEST_PAGE_SIZE;

  return (
    <div className="space-y-4">
      <section className="rounded-[1.25rem] border border-zinc-200 bg-white p-5 shadow-[0_18px_50px_-44px_rgba(15,23,42,0.35)]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-blue-600">Backtest Registry</div>
            <h1 className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-zinc-950">回测记录</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-600">
              这里会合并读取 reports 下各个 RunRegistry 的 SQLite 表。每次 workflow 跑完后会把 manifest、指标、交易明细和报告路径写入对应回测表，并展示在这里。
            </p>
          </div>
        </div>
      </section>

      {initialError ? (
        <div className="rounded-[1rem] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{initialError}</div>
      ) : null}

      <BacktestsClient initialRecords={recordsForDisplay} initialHasMore={hasMore} />
    </div>
  );
}
