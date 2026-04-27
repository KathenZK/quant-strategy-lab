import { fetchStrategyLabJson, STRATEGY_LAB_ENDPOINTS } from "../lib/strategy-lab-api";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "总览",
  description: "量化策略实验平台总览，聚合行情、数据源、策略实验与回测记录。",
};

function formatPct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return `${(Number(value) * 100).toFixed(2)}%`;
}

function bestRun(runs) {
  return [...runs].sort((left, right) => (right.backtest_metrics?.sharpe ?? -999) - (left.backtest_metrics?.sharpe ?? -999))[0];
}

async function loadDashboardData() {
  const [runsPayload, tickersPayload, sourcesPayload, newsPayload] = await Promise.allSettled([
    fetchStrategyLabJson(STRATEGY_LAB_ENDPOINTS.runs),
    fetchStrategyLabJson(STRATEGY_LAB_ENDPOINTS.marketTickers, { searchParams: { source: "binance", limit: 8 } }),
    fetchStrategyLabJson(STRATEGY_LAB_ENDPOINTS.marketSources),
    fetchStrategyLabJson(STRATEGY_LAB_ENDPOINTS.newsEvents, { searchParams: { limit: 4 } }),
  ]);

  return {
    runs: runsPayload.status === "fulfilled" ? (runsPayload.value.runs ?? []) : [],
    tickers: tickersPayload.status === "fulfilled" ? (tickersPayload.value.tickers ?? []) : [],
    sources: sourcesPayload.status === "fulfilled" ? (sourcesPayload.value.sources ?? []) : [],
    events: newsPayload.status === "fulfilled" ? (newsPayload.value.events ?? []) : [],
  };
}

export default async function HomePage() {
  const { runs, tickers, sources, events } = await loadDashboardData();
  const winner = bestRun(runs);
  const onlineSources = sources.filter((source) => ["online", "ready"].includes(source.status)).length;

  return (
    <div className="space-y-4">
      <section className="grid gap-3 md:grid-cols-4">
        {[
          ["策略实验", "3", "模板化创建入口"],
          ["数据源", `${onlineSources}/${sources.length || 1}`, "Binance / OKX / Data Lake"],
          ["回测记录", String(runs.length), "运行注册表"],
          ["新闻事件", String(events.length), "事件交易研究输入"],
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
              <div className="mt-1 font-mono text-xl font-semibold text-zinc-950">{winner?.backtest_metrics?.sharpe ?? "-"}</div>
            </div>
            <div className="rounded-lg bg-zinc-50 p-3">
              <div className="text-xs text-zinc-500">当前最佳策略</div>
              <div className="mt-1 truncate text-sm font-semibold text-zinc-950">{winner?.variant_id || winner?.strategy_type || "暂无回测结果"}</div>
            </div>
          </div>
          <div className="mt-4 border-t border-zinc-100 pt-4">
            <div className="mb-3 text-sm font-semibold text-zinc-950">轻量观察标的</div>
            <div className="grid gap-2 md:grid-cols-4">
              {tickers.slice(0, 4).map((ticker) => (
                <div key={`${ticker.source}-${ticker.symbol}`} className="rounded-lg border border-zinc-200 bg-white px-3 py-2">
                  <div className="text-sm font-semibold text-zinc-950">{ticker.symbol}</div>
                  <div className="mt-1 flex items-center justify-between gap-2 text-xs">
                    <span className="font-mono text-zinc-600">{ticker.last}</span>
                    <span className={`font-mono font-semibold ${ticker.change_24h >= 0 ? "text-[#16a05d]" : "text-[#d93025]"}`}>
                      {formatPct(ticker.change_24h)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="lab-card p-4">
          <div className="border-b border-zinc-100 pb-3 text-base font-semibold text-zinc-950">快讯 / 事件</div>
          <div className="mt-3 space-y-3">
            {events.map((event) => (
              <a key={event.id} href="/news" className="block border-b border-zinc-100 pb-3 last:border-0 last:pb-0">
                <div className="text-sm font-medium leading-5 text-zinc-950">{event.title}</div>
                <div className="mt-1 text-xs text-zinc-500">{event.assets.join(" / ")}</div>
              </a>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
