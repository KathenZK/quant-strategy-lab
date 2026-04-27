import { fetchStrategyLabJson, STRATEGY_LAB_ENDPOINTS } from "../../lib/strategy-lab-api";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "新闻事件",
  description: "新闻流、事件标签、相关币种与事件交易研究入口。",
};

function sentimentLabel(value) {
  if (value >= 0.6) {
    return "positive";
  }
  if (value <= 0.45) {
    return "defensive";
  }
  return "neutral";
}

export default async function NewsPage() {
  let events = [];
  try {
    const payload = await fetchStrategyLabJson(STRATEGY_LAB_ENDPOINTS.newsEvents);
    events = payload.events ?? [];
  } catch {
    events = [];
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_360px]">
      <section className="lab-card p-4">
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">News intelligence</div>
        <h1 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-zinc-950">新闻事件</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-600">第一阶段先把新闻作为研究输入：标记资产、事件类型和时间窗口，后续再进入事件因子与事件回测。</p>

        <div className="mt-6 space-y-4">
          {events.length > 0 ? (
            events.map((event) => (
              <article key={event.id} className="rounded-lg border border-zinc-200 bg-zinc-50 p-4">
                <div className="flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-zinc-500">
                  <span>{event.source}</span>
                  <span>·</span>
                  <span>{new Date(event.published_at).toLocaleString("zh-CN", { hour12: false })}</span>
                  <span className="rounded border border-zinc-200 bg-white px-2 py-0.5">{event.event_type}</span>
                </div>
                <h2 className="mt-3 text-xl font-semibold text-zinc-950">{event.title}</h2>
                <p className="mt-2 text-sm leading-6 text-zinc-600">{event.summary}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {event.assets.map((asset) => (
                    <span key={asset} className="rounded bg-blue-50 px-3 py-1 text-xs font-semibold text-[#1f6feb]">
                      {asset}
                    </span>
                  ))}
                  <span className="rounded bg-white px-3 py-1 text-xs text-zinc-600">{sentimentLabel(event.sentiment)}</span>
                </div>
              </article>
            ))
          ) : (
            <div className="rounded-lg border border-dashed border-zinc-300 bg-zinc-50 p-5 text-sm leading-6 text-zinc-600">
              当前没有配置真实新闻/事件数据源，所以这里不再展示模拟快讯。后续接入 RSS、交易所公告或新闻 API 后，事件会从真实源写入并展示。
            </div>
          )}
        </div>
      </section>

      <aside className="space-y-5">
        <div className="lab-card p-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">Event trading model</div>
          <h2 className="mt-2 text-xl font-semibold text-zinc-950">事件交易预留模型</h2>
          <div className="mt-4 space-y-3 text-sm leading-6 text-zinc-600">
            <p>1. 新闻归一化为事件，保留发布时间、来源、资产标签和情绪分。</p>
            <p>2. 事件窗口映射到行情 bar，生成事件后收益、最大回撤和成交量冲击。</p>
            <p>3. 通过策略实验室验证规则，不直接从新闻触发交易。</p>
          </div>
        </div>
        <div className="lab-card p-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">Asset coverage</div>
          {events.length > 0 ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {[...new Set(events.flatMap((event) => event.assets))].map((asset) => (
                <span key={asset} className="rounded border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-700">
                  {asset}
                </span>
              ))}
            </div>
          ) : (
            <p className="mt-4 text-sm leading-6 text-zinc-500">暂无真实事件资产覆盖。</p>
          )}
        </div>
      </aside>
    </div>
  );
}
