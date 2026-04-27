import { fetchSignalLabJson, SIGNAL_LAB_ENDPOINTS } from "../../lib/signal-lab-api";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "数据源",
  description: "查看 Binance、OKX、本地数据湖与新闻事件源的连接状态。",
};

export default async function DataSourcesPage() {
  let sources = [];
  try {
    const payload = await fetchSignalLabJson(SIGNAL_LAB_ENDPOINTS.marketSources);
    sources = payload.sources ?? [];
  } catch {
    sources = [];
  }

  return (
    <div className="space-y-5">
      <section className="rounded-[1.75rem] border border-zinc-200 bg-white p-5 shadow-[0_24px_80px_-60px_rgba(37,61,56,0.28)]">
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">Connectors</div>
        <h1 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-zinc-950">数据源</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-600">把交易所行情、本地数据湖和新闻事件源统一展示。后续股票和预测市场也会作为同一种 Instrument 接口接入。</p>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {sources.map((source) => (
          <article key={source.id} className="rounded-[1.5rem] border border-zinc-200 bg-white p-4 shadow-[0_24px_80px_-60px_rgba(37,61,56,0.28)]">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-[11px] uppercase tracking-[0.16em] text-zinc-500">{source.type}</div>
                <h2 className="mt-2 text-xl font-semibold text-zinc-950">{source.name}</h2>
              </div>
              <span className={`rounded-full px-2 py-1 text-[11px] ${source.status === "planned" ? "bg-amber-50 text-amber-700" : "bg-emerald-50 text-emerald-700"}`}>
                {source.status}
              </span>
            </div>
            <p className="mt-4 min-h-12 text-sm leading-6 text-zinc-600">{source.note}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {source.coverage.map((item) => (
                <span key={item} className="rounded-full border border-zinc-200 bg-zinc-50 px-2 py-1 text-[11px] text-zinc-600">
                  {item}
                </span>
              ))}
            </div>
            <div className="mt-5 border-t border-zinc-200 pt-3 text-xs text-zinc-500">
              latency: {source.latency_ms === null ? "n/a" : `${source.latency_ms}ms`}
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}
