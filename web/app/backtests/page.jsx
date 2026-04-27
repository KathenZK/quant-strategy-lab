import { fetchStrategyLabJson, STRATEGY_LAB_ENDPOINTS } from "../../lib/strategy-lab-api";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "回测记录",
  description: "查看策略回测批次、核心指标与运行指纹。",
};

const strategyLabels = {
  crowding_reversal: "拥挤度反转",
  donchian_breakout: "Donchian 突破",
  ma_crossover: "双均线交叉",
  momentum_rotation: "动量轮动",
  trend_confirmation: "趋势确认",
};

const numberFormat = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 2,
});

const compactNumberFormat = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 4,
});

const dateFormat = new Intl.DateTimeFormat("zh-CN", {
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function metric(run, key) {
  const value = run?.backtest_metrics?.[key] ?? run?.[key];
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : null;
}

function formatNumber(value, fallback = "-") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return fallback;
  }
  return numberFormat.format(Number(value));
}

function formatMetric(value, fallback = "-") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return fallback;
  }
  return compactNumberFormat.format(Number(value));
}

function formatPercent(value, fallback = "-") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return fallback;
  }
  return `${(Number(value) * 100).toFixed(2)}%`;
}

function formatDate(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "-" : dateFormat.format(date);
}

function shortHash(value) {
  return value ? String(value).slice(0, 10) : "-";
}

function shortPath(value) {
  if (!value) {
    return "-";
  }
  const text = String(value);
  const marker = "/reports/";
  const index = text.indexOf(marker);
  return index >= 0 ? `reports/${text.slice(index + marker.length)}` : text;
}

function strategyLabel(run) {
  const key = run.strategy_type || run.signal_name || run.name;
  return strategyLabels[key] || key || "-";
}

function runSearchText(run) {
  return [run.name, run.strategy_name, run.backtest_report_path, run.manifest_path, run.registry_profile]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function runWindow(run) {
  const searchable = runSearchText(run);
  if (searchable.includes("recent1y_daily") || searchable.includes("daily_recent1y") || searchable.includes("recent1y-daily")) {
    return "1y daily";
  }
  if (searchable.includes("recent3m")) {
    return "3m 1h";
  }
  if (searchable.includes("recent1y")) {
    return "1y";
  }
  return run.registry_profile || "registry";
}

function ReturnValue({ value }) {
  const tone = Number(value) >= 0 ? "text-emerald-600" : "text-red-600";
  return <span className={tone}>{formatPercent(value)}</span>;
}

function BacktestTable({ records }) {
  if (records.length === 0) {
    return (
      <div className="rounded-[1rem] border border-dashed border-zinc-300 bg-white p-8 text-sm text-zinc-500">
        暂时没有回测记录。运行策略 workflow 后会自动写入这里。
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-[1rem] border border-zinc-200 bg-white shadow-[0_18px_50px_-42px_rgba(15,23,42,0.45)]">
      <div className="overflow-x-auto">
        <table className="min-w-[1160px] text-left text-sm">
          <thead className="border-b border-zinc-200 bg-zinc-50 text-[11px] uppercase tracking-[0.14em] text-zinc-500">
            <tr>
              <th className="w-[250px] whitespace-nowrap px-4 py-3 font-semibold">策略</th>
              <th className="w-[170px] whitespace-nowrap px-4 py-3 font-semibold">运行时间</th>
              <th className="whitespace-nowrap px-4 py-3 text-right font-semibold">累计收益</th>
              <th className="whitespace-nowrap px-4 py-3 text-right font-semibold">Sharpe</th>
              <th className="whitespace-nowrap px-4 py-3 text-right font-semibold">最大回撤</th>
              <th className="whitespace-nowrap px-4 py-3 text-right font-semibold">换手</th>
              <th className="whitespace-nowrap px-4 py-3 text-right font-semibold">交易</th>
              <th className="w-[320px] whitespace-nowrap px-4 py-3 font-semibold">运行指纹</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {records.map((run) => (
              <tr key={run.manifest_path || run.run_id} className="align-top hover:bg-blue-50/40">
                <td className="px-4 py-4">
                  <div className="font-semibold text-zinc-950">{strategyLabel(run)}</div>
                  <div className="mt-1 text-xs text-zinc-500">{run.name}</div>
                </td>
                <td className="whitespace-nowrap px-4 py-4 text-zinc-700">
                  <div>{formatDate(run.generated_at)}</div>
                  <div className="mt-1 text-xs text-zinc-500">Binance perp · {runWindow(run)}</div>
                </td>
                <td className="whitespace-nowrap px-4 py-4 text-right font-semibold">
                  <ReturnValue value={metric(run, "cumulative_return")} />
                </td>
                <td className="whitespace-nowrap px-4 py-4 text-right text-zinc-800">{formatMetric(metric(run, "sharpe"))}</td>
                <td className="whitespace-nowrap px-4 py-4 text-right font-semibold text-red-600">
                  {formatPercent(metric(run, "max_drawdown"))}
                </td>
                <td className="whitespace-nowrap px-4 py-4 text-right text-zinc-700">{formatPercent(metric(run, "avg_turnover"))}</td>
                <td className="whitespace-nowrap px-4 py-4 text-right text-zinc-700">
                  {formatNumber(run.trade_count ?? run.fill_count)}
                </td>
                <td className="px-4 py-4">
                  <div className="font-mono text-xs text-zinc-800">{shortHash(run.run_id)}</div>
                  <div className="mt-1 max-w-[260px] truncate font-mono text-[11px] text-zinc-500">
                    {shortPath(run.backtest_report_path)}
                  </div>
                  <div className="mt-1 text-[11px] text-zinc-500">snapshot {shortHash(run.data_snapshot_id)}</div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default async function BacktestsPage() {
  let runs = [];
  let initialError = "";

  try {
    const searchParams = new URLSearchParams({
      kind: "workflow_run",
      limit: "200",
      sort_by: "generated_at",
      sort_order: "desc",
    });
    const payload = await fetchStrategyLabJson(STRATEGY_LAB_ENDPOINTS.runs, { searchParams });
    runs = payload.runs ?? [];
  } catch (error) {
    initialError = error instanceof Error ? error.message : "Failed to load runs.";
  }

  const recordsForDisplay = runs;

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

      <section className="space-y-3">
        <h2 className="text-base font-semibold text-zinc-950">全部回测记录</h2>
        <BacktestTable records={recordsForDisplay} />
      </section>
    </div>
  );
}
