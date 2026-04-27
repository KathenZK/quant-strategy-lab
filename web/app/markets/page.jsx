import { fetchSignalLabJson, SIGNAL_LAB_ENDPOINTS } from "../../lib/signal-lab-api";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "行情",
  description: "查看 Binance/OKX 币种行情、K 线、资金费率和 OI。",
};

function pct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return `${(Number(value) * 100).toFixed(2)}%`;
}

function fmt(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return Number(value).toLocaleString("en-US", { maximumFractionDigits: Number(value) < 1 ? 6 : 2 });
}

function sparklinePath(bars) {
  if (!bars.length) {
    return "";
  }
  const values = bars.map((bar) => Number(bar.close));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  return values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * 620;
      const y = 220 - ((value - min) / span) * 180;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

async function loadMarkets() {
  const [sourcesPayload, tickersPayload, ohlcvPayload] = await Promise.allSettled([
    fetchSignalLabJson(SIGNAL_LAB_ENDPOINTS.marketSources),
    fetchSignalLabJson(SIGNAL_LAB_ENDPOINTS.marketTickers, { searchParams: { source: "binance", limit: 40 } }),
    fetchSignalLabJson(SIGNAL_LAB_ENDPOINTS.marketOhlcv, { searchParams: { source: "binance", symbol: "BTC/USDT", timeframe: "1h", limit: 90 } }),
  ]);
  return {
    sources: sourcesPayload.status === "fulfilled" ? (sourcesPayload.value.sources ?? []) : [],
    tickers: tickersPayload.status === "fulfilled" ? (tickersPayload.value.tickers ?? []) : [],
    bars: ohlcvPayload.status === "fulfilled" ? (ohlcvPayload.value.bars ?? []) : [],
  };
}

export default async function MarketsPage() {
  const { sources, tickers, bars } = await loadMarkets();
  const btc = tickers.find((ticker) => ticker.symbol === "BTC/USDT") ?? tickers[0];
  const path = sparklinePath(bars);

  return (
    <div className="space-y-5">
      <section className="grid gap-5 xl:grid-cols-[360px_1fr]">
        <div className="rounded-[1.75rem] border border-zinc-200 bg-white p-5 shadow-[0_24px_80px_-60px_rgba(37,61,56,0.28)]">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">Data sources</div>
          <h1 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-zinc-950">行情中心</h1>
          <p className="mt-3 text-sm leading-6 text-zinc-600">第一阶段同时服务实时观察和策略实验：行情页使用缓存 ticker，回测使用数据快照。</p>
          <div className="mt-5 space-y-3">
            {sources.slice(0, 3).map((source) => (
              <div key={source.id} className="rounded-2xl border border-zinc-200 bg-zinc-50 p-3">
                <div className="flex items-center justify-between">
                  <div className="font-semibold text-zinc-950">{source.name}</div>
                  <span className="rounded-full bg-emerald-50 px-2 py-1 text-[11px] text-emerald-700">{source.status}</span>
                </div>
                <div className="mt-2 text-xs leading-5 text-zinc-500">{source.coverage.join(" / ")}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-[1.75rem] border border-zinc-200 bg-white p-5 shadow-[0_24px_80px_-60px_rgba(37,61,56,0.28)]">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">BTC/USDT · 1h</div>
              <div className="mt-2 flex items-end gap-3">
                <h2 className="font-mono text-4xl font-semibold tabular-nums text-zinc-950">{fmt(btc?.last)}</h2>
                <span className={btc?.change_24h >= 0 ? "pb-1 font-mono text-emerald-600" : "pb-1 font-mono text-rose-600"}>{pct(btc?.change_24h)}</span>
              </div>
            </div>
            <div className="rounded-2xl border border-zinc-200 bg-zinc-50 px-4 py-3 text-right">
              <div className="text-xs text-zinc-500">Quote volume</div>
              <div className="mt-1 font-mono text-lg font-semibold tabular-nums text-zinc-950">{fmt(btc?.quote_volume_24h)}</div>
            </div>
          </div>
          <svg viewBox="0 0 640 260" role="img" aria-label="BTC 价格走势" className="mt-5 h-[260px] w-full overflow-visible rounded-[1.25rem] bg-zinc-50">
            <path d="M 0 220 H 640 M 0 160 H 640 M 0 100 H 640 M 0 40 H 640" stroke="rgba(24,24,27,0.08)" strokeWidth="1" />
            <path d={path} fill="none" stroke="rgb(15 118 110)" strokeLinecap="round" strokeWidth="3" />
          </svg>
        </div>
      </section>

      <section className="overflow-hidden rounded-[1.75rem] border border-zinc-200 bg-white shadow-[0_24px_80px_-60px_rgba(37,61,56,0.28)]">
        <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-4">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">Watchlist</div>
            <h2 className="mt-1 text-xl font-semibold text-zinc-950">币种行情列表</h2>
          </div>
          <div className="rounded-full border border-zinc-200 px-3 py-1.5 text-xs text-zinc-500">Binance first · OKX ready</div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="bg-zinc-50 text-[11px] uppercase tracking-[0.14em] text-zinc-500">
              <tr>
                <th className="px-5 py-3">Symbol</th>
                <th className="px-5 py-3">Source</th>
                <th className="px-5 py-3">Market</th>
                <th className="px-5 py-3">Last</th>
                <th className="px-5 py-3">24h</th>
                <th className="px-5 py-3">Funding</th>
                <th className="px-5 py-3">Open interest</th>
                <th className="px-5 py-3">Quote volume</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {tickers.map((ticker) => (
                <tr key={`${ticker.source}-${ticker.symbol}`} className="text-zinc-700 hover:bg-zinc-50">
                  <td className="px-5 py-3 font-semibold text-zinc-950">{ticker.symbol}</td>
                  <td className="px-5 py-3">{ticker.source.toUpperCase()}</td>
                  <td className="px-5 py-3">{ticker.market_type}</td>
                  <td className="px-5 py-3 font-mono tabular-nums">{fmt(ticker.last)}</td>
                  <td className={`px-5 py-3 font-mono tabular-nums ${ticker.change_24h >= 0 ? "text-emerald-600" : "text-rose-600"}`}>{pct(ticker.change_24h)}</td>
                  <td className="px-5 py-3 font-mono tabular-nums">{ticker.funding_rate === null ? "-" : pct(ticker.funding_rate)}</td>
                  <td className="px-5 py-3 font-mono tabular-nums">{fmt(ticker.open_interest)}</td>
                  <td className="px-5 py-3 font-mono tabular-nums">{fmt(ticker.quote_volume_24h)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
