import { fetchStrategyLabJson, STRATEGY_LAB_ENDPOINTS } from "../lib/strategy-lab-api";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "总览",
  description: "量化策略实验平台总览，聚合真实数据湖、策略注册表与回测记录。",
};

function formatPct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return `${(Number(value) * 100).toFixed(2)}%`;
}

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return new Intl.NumberFormat("en-US").format(Number(value));
}

function formatMetric(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return Number(value).toFixed(4);
}

function bestRun(runs) {
  return [...runs].sort((left, right) => (right.backtest_metrics?.sharpe ?? -999) - (left.backtest_metrics?.sharpe ?? -999))[0];
}

function sourceStatusClass(status) {
  if (status === "ready") {
    return "bg-emerald-50 text-emerald-700";
  }
  if (status === "configured") {
    return "bg-blue-50 text-blue-700";
  }
  return "bg-zinc-100 text-zinc-500";
}

async function loadDashboardData() {
  const [runsPayload, tickersPayload, sourcesPayload, templatesPayload] = await Promise.allSettled([
    fetchStrategyLabJson(STRATEGY_LAB_ENDPOINTS.runs, {
      searchParams: { kind: "workflow_run", limit: 200, sort_by: "generated_at", sort_order: "desc" },
    }),
    fetchStrategyLabJson(STRATEGY_LAB_ENDPOINTS.marketTickers, { searchParams: { source: "binance", limit: 8 } }),
    fetchStrategyLabJson(STRATEGY_LAB_ENDPOINTS.marketSources),
    fetchStrategyLabJson(STRATEGY_LAB_ENDPOINTS.strategyTemplates),
  ]);

  return {
    runs: runsPayload.status === "fulfilled" ? (runsPayload.value.runs ?? []) : [],
    tickers: tickersPayload.status === "fulfilled" ? (tickersPayload.value.tickers ?? []) : [],
    sources: sourcesPayload.status === "fulfilled" ? (sourcesPayload.value.sources ?? []) : [],
    templates: templatesPayload.status === "fulfilled" ? (templatesPayload.value.templates ?? []) : [],
  };
}

export default async function HomePage() {
  const { runs, tickers, sources, templates } = await loadDashboardData();
  const winner = bestRun(runs);
  const readySources = sources.filter((source) => source.status === "ready").length;
  const trackedSymbols = new Set(tickers.map((ticker) => ticker.symbol)).size;
  const dataLakeSource = sources.find((source) => source.id === "data_lake");

  return (
    <div className="space-y-4">
      <section className="grid gap-3 md:grid-cols-4">
        {[
          ["策略模板", String(templates.length), "来自后端 strategy_registry"],
          ["真实数据源", `${readySources}/${sources.length || 1}`, "读取当前配置和数据湖"],
          ["回测记录", String(runs.length), "SQLite RunRegistry"],
          ["数据湖标的", String(trackedSymbols || dataLakeSource?.symbol_count || 0), "normalized OHLCV"],
        ].map(([label, value, note]) => (
          <div key={label} className="lab-card px-4 py-3">
            <div className="text-xs text-zinc-500">{label}</div>
            <div className="mt-2 font-mono text-xl font-semibold tabular-nums text-zinc-950">{value}</div>
            <div className="mt-1 text-xs text-zinc-400">{note}</div>
          </div>
        ))}
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <div className="lab-card p-4">
          <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
            <h2 className="text-base font-semibold text-zinc-950">策略实验概览</h2>
            <a href="/lab" className="text-sm text-[#1f6feb] hover:underline">
              创建策略实验
            </a>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <div className="rounded-lg bg-zinc-50 p-3">
              <div className="text-xs text-zinc-500">回测记录</div>
              <div className="mt-1 font-mono text-xl font-semibold text-zinc-950">{runs.length}</div>
            </div>
            <div className="rounded-lg bg-zinc-50 p-3">
              <div className="text-xs text-zinc-500">Best Sharpe</div>
              <div className="mt-1 font-mono text-xl font-semibold text-zinc-950">{formatMetric(winner?.backtest_metrics?.sharpe)}</div>
            </div>
            <div className="rounded-lg bg-zinc-50 p-3">
              <div className="text-xs text-zinc-500">当前最佳策略</div>
              <div className="mt-1 truncate text-sm font-semibold text-zinc-950">{winner?.variant_id || winner?.strategy_type || "暂无回测结果"}</div>
            </div>
          </div>
          <div className="mt-4 border-t border-zinc-100 pt-4">
            <div className="mb-3 text-sm font-semibold text-zinc-950">真实行情快照</div>
            {tickers.length > 0 ? (
              <div className="grid gap-2 md:grid-cols-4">
                {tickers.slice(0, 4).map((ticker) => (
                  <div key={`${ticker.source}-${ticker.symbol}-${ticker.market_type}`} className="rounded-lg border border-zinc-200 bg-white px-3 py-2">
                    <div className="text-sm font-semibold text-zinc-950">{ticker.symbol}</div>
                    <div className="mt-1 flex items-center justify-between gap-2 text-xs">
                      <span className="font-mono text-zinc-600">{formatNumber(ticker.last)}</span>
                      <span className={`font-mono font-semibold ${ticker.change_24h >= 0 ? "text-[#16a05d]" : "text-[#d93025]"}`}>
                        {formatPct(ticker.change_24h)}
                      </span>
                    </div>
                    <div className="mt-1 truncate text-[11px] text-zinc-400">updated {ticker.updated_at || "-"}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-lg border border-dashed border-zinc-300 bg-zinc-50 px-3 py-4 text-sm text-zinc-500">
                当前数据湖没有可展示的 normalized OHLCV 快照。
              </div>
            )}
          </div>
        </div>

        <div className="lab-card p-4">
          <div className="border-b border-zinc-100 pb-3 text-base font-semibold text-zinc-950">真实数据源状态</div>
          <div className="mt-3 space-y-3">
            {sources.map((source) => (
              <a key={source.id} href="/data-sources" className="block border-b border-zinc-100 pb-3 last:border-0 last:pb-0">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium leading-5 text-zinc-950">{source.name}</div>
                    <div className="mt-1 text-xs text-zinc-500">
                      {formatNumber(source.row_count)} rows · {formatNumber(source.symbol_count)} symbols
                    </div>
                  </div>
                  <span className={`rounded px-2 py-1 text-[11px] ${sourceStatusClass(source.status)}`}>{source.status}</span>
                </div>
                <div className="mt-2 line-clamp-2 text-xs leading-5 text-zinc-500">{source.note}</div>
              </a>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
