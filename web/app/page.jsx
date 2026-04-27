import { fetchSignalLabJson, SIGNAL_LAB_ENDPOINTS } from "../lib/signal-lab-api";

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
    fetchSignalLabJson(SIGNAL_LAB_ENDPOINTS.runs),
    fetchSignalLabJson(SIGNAL_LAB_ENDPOINTS.marketTickers, { searchParams: { source: "binance", limit: 8 } }),
    fetchSignalLabJson(SIGNAL_LAB_ENDPOINTS.marketSources),
    fetchSignalLabJson(SIGNAL_LAB_ENDPOINTS.newsEvents, { searchParams: { limit: 4 } }),
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
    <div className="space-y-5">
      <section className="overflow-hidden rounded-[2rem] border border-zinc-200 bg-white shadow-[0_36px_110px_-74px_rgba(37,61,56,0.32)]">
        <div className="grid gap-8 p-6 lg:grid-cols-[1fr_360px] lg:p-8">
          <div>
            <div className="inline-flex rounded-full border border-teal-200 bg-teal-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-teal-700">
              Research command center
            </div>
            <h1 className="mt-5 max-w-4xl text-balance text-4xl font-semibold tracking-[-0.06em] text-zinc-950 md:text-6xl">
              从行情和事件发现机会，在策略实验室里验证。
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-zinc-600">
              第一阶段先服务个人/小团队：行情页偏实时，回测使用可复现数据快照，所有实验结果沉淀到统一运行注册表。
            </p>
          </div>
          <div className="rounded-[1.6rem] border border-zinc-200 bg-zinc-50 p-4">
            <div className="text-[11px] uppercase tracking-[0.18em] text-zinc-500">Platform state</div>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded-2xl border border-zinc-200 bg-white p-3">
                <div className="text-xs text-zinc-500">数据源</div>
                <div className="mt-1 font-mono text-2xl font-semibold tabular-nums text-zinc-950">{onlineSources}</div>
              </div>
              <div className="rounded-2xl border border-zinc-200 bg-white p-3">
                <div className="text-xs text-zinc-500">回测记录</div>
                <div className="mt-1 font-mono text-2xl font-semibold tabular-nums text-zinc-950">{runs.length}</div>
              </div>
              <div className="rounded-2xl border border-zinc-200 bg-white p-3">
                <div className="text-xs text-zinc-500">观察标的</div>
                <div className="mt-1 font-mono text-2xl font-semibold tabular-nums text-zinc-950">{tickers.length}</div>
              </div>
              <div className="rounded-2xl border border-zinc-200 bg-white p-3">
                <div className="text-xs text-zinc-500">事件流</div>
                <div className="mt-1 font-mono text-2xl font-semibold tabular-nums text-zinc-950">{events.length}</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-[1.75rem] border border-zinc-200 bg-white p-5 shadow-[0_24px_80px_-60px_rgba(37,61,56,0.28)]">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">Market watch</div>
              <h2 className="mt-1 text-xl font-semibold text-zinc-950">Binance/OKX 行情入口</h2>
            </div>
            <a href="/markets" className="rounded-full border border-zinc-200 px-3 py-1.5 text-xs text-zinc-600 hover:bg-zinc-50">
              查看行情
            </a>
          </div>
          <div className="mt-4 overflow-hidden rounded-2xl border border-zinc-200">
            <table className="w-full text-left text-sm">
              <thead className="bg-zinc-50 text-[11px] uppercase tracking-[0.14em] text-zinc-500">
                <tr>
                  <th className="px-4 py-3">Symbol</th>
                  <th className="px-4 py-3">Last</th>
                  <th className="px-4 py-3">24h</th>
                  <th className="px-4 py-3">Volume</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {tickers.slice(0, 6).map((ticker) => (
                  <tr key={`${ticker.source}-${ticker.symbol}`} className="text-zinc-700">
                    <td className="px-4 py-3 font-semibold text-zinc-950">{ticker.symbol}</td>
                    <td className="px-4 py-3 font-mono tabular-nums">{ticker.last}</td>
                    <td className={`px-4 py-3 font-mono tabular-nums ${ticker.change_24h >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                      {formatPct(ticker.change_24h)}
                    </td>
                    <td className="px-4 py-3 font-mono tabular-nums">{Math.round(ticker.quote_volume_24h).toLocaleString("en-US")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="space-y-5">
          <div className="rounded-[1.75rem] border border-zinc-200 bg-white p-5 shadow-[0_24px_80px_-60px_rgba(37,61,56,0.28)]">
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">Best run</div>
            <h2 className="mt-2 text-xl font-semibold text-zinc-950">{winner?.variant_id || winner?.strategy_type || "暂无回测结果"}</h2>
            <div className="mt-4 grid grid-cols-3 gap-3">
              {["sharpe", "cumulative_return", "max_drawdown"].map((key) => (
                <div key={key} className="rounded-2xl border border-zinc-200 bg-zinc-50 p-3">
                  <div className="text-xs text-zinc-500">{key}</div>
                  <div className="mt-1 font-mono text-sm font-semibold tabular-nums text-zinc-950">
                    {key === "sharpe" ? (winner?.backtest_metrics?.[key] ?? "-") : formatPct(winner?.backtest_metrics?.[key])}
                  </div>
                </div>
              ))}
            </div>
            <a href="/backtests" className="mt-4 inline-flex rounded-full bg-teal-300 px-4 py-2 text-sm font-semibold text-zinc-950 hover:bg-teal-200">
              进入回测记录
            </a>
          </div>

          <div className="rounded-[1.75rem] border border-zinc-200 bg-white p-5 shadow-[0_24px_80px_-60px_rgba(37,61,56,0.28)]">
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">News events</div>
            <div className="mt-4 space-y-3">
              {events.map((event) => (
                <a key={event.id} href="/news" className="block rounded-2xl border border-zinc-200 bg-zinc-50 p-3 hover:bg-white">
                  <div className="text-sm font-medium text-zinc-950">{event.title}</div>
                  <div className="mt-1 text-xs text-zinc-500">{event.assets.join(" / ")}</div>
                </a>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
