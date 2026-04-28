"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ChartLineUp, Flask, ListChecks, Scales, TrendUp } from "@phosphor-icons/react";

import {
  buildStrategyGroups,
  costRatioOf,
  formatDate,
  formatMetric,
  formatNumber,
  formatPercent,
  metricOf,
  parameterSummary,
  runIdentity,
  runVariantId,
  runWindow,
  shortHash,
  strategyKeyFromTemplate,
  strategyParamsOf,
} from "../../lib/strategy-workbench";

const metricColumns = [
  { key: "cumulative_return", label: "累计收益", kind: "percent", strong: true },
  { key: "buy_hold_return", label: "BTC持有", kind: "percent" },
  { key: "excess_return_vs_buy_hold", label: "超额", kind: "percent", strong: true },
  { key: "annualized_return", label: "年化", kind: "percent" },
  { key: "max_drawdown", label: "最大回撤", kind: "percent", bad: true },
  { key: "sharpe", label: "Sharpe", kind: "number" },
  { key: "calmar", label: "Calmar", kind: "number" },
  { key: "win_rate", label: "胜率", kind: "percent" },
  { key: "profit_loss_ratio", label: "盈亏比", kind: "number" },
  { key: "avg_turnover", label: "换手率", kind: "number" },
  { key: "fee_ratio", label: "费用占比", kind: "percent" },
];

const parameterLabels = {
  fast_ma_factor: "快均线因子",
  slow_ma_factor: "慢均线因子",
  long_allocation: "多头仓位",
  short_allocation: "空头仓位",
  stop_loss_pct: "止损比例",
  take_profit_pct: "止盈比例",
  cooldown_bars: "冷却 bar 数",
  min_ma_gap_ratio: "最小均线差",
  min_slow_ma_slope: "最小慢线斜率",
  slope_lookback: "斜率窗口",
  exit_on_choppy: "震荡退出",
  primary_momentum_factor: "主动量因子",
  fast_momentum_factor: "快速动量因子",
  confirmation_momentum_factor: "确认动量因子",
  breakout_factor: "突破因子",
  rsi_factor: "RSI 因子",
  volume_factor: "成交量因子",
  illiquidity_factor: "流动性惩罚因子",
  funding_zscore_factor: "资金费率 zscore",
  min_breakout_signal: "最小突破信号",
  min_fast_momentum: "最小快速动量",
  min_confirmation_momentum: "最小确认动量",
  min_volume_surge: "最小放量",
  min_rsi: "RSI 下限",
  max_rsi: "RSI 上限",
  max_amihud_illiquidity: "最大 Amihud 非流动性",
  max_long_positions: "最大多头数",
  max_short_positions: "最大空头数",
  max_positions: "最大持仓数",
  position_weight: "单币仓位",
  trailing_stop_pct: "移动止盈回撤",
  max_hold_bars: "最长持仓 bar 数",
  market_neutral: "市场中性",
  risk_budget_pct: "风险预算",
  max_pyramids: "最大加仓次数",
};

function valueFor(run, key) {
  if (key === "fee_ratio") {
    return costRatioOf(run);
  }
  return metricOf(run, key);
}

function formatValue(value, kind) {
  return kind === "percent" ? formatPercent(value) : formatMetric(value);
}

function toneFor(value, column) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "text-zinc-400 dark:text-slate-500";
  }
  if (column.bad) {
    return Number(value) < 0 ? "text-rose-600 dark:text-rose-300" : "text-zinc-800 dark:text-slate-200";
  }
  if (["cumulative_return", "annualized_return", "excess_return_vs_buy_hold", "sharpe", "calmar"].includes(column.key)) {
    return Number(value) >= 0 ? "text-emerald-700 dark:text-emerald-300" : "text-rose-600 dark:text-rose-300";
  }
  return "text-zinc-800 dark:text-slate-200";
}

function bestByMetric(runs, key) {
  const scored = runs.filter((run) => valueFor(run, key) !== null);
  if (!scored.length) {
    return null;
  }
  return [...scored].sort((left, right) => valueFor(right, key) - valueFor(left, key))[0];
}

function StrategyRail({ groups, selectedKey, onSelect }) {
  return (
    <aside className="space-y-3">
      <section className="lab-card p-4">
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-teal-700 dark:text-teal-300">Results Console</div>
        <h1 className="mt-2 text-3xl font-semibold tracking-[-0.05em] text-zinc-950 dark:text-zinc-100">策略实验室</h1>
        <p className="mt-3 text-sm leading-6 text-zinc-600 dark:text-slate-400">策略在 IDE/CLI 里开发和运行，这里只负责展示记录、参数、指标和对比。</p>
      </section>

      <section className="lab-card overflow-hidden">
        <div className="border-b border-zinc-200 px-4 py-3 text-xs font-semibold text-zinc-500 dark:border-slate-800 dark:text-slate-500">策略族</div>
        <div className="max-h-[calc(100dvh-310px)] space-y-1 overflow-y-auto p-2">
          {groups.map((group) => {
            const active = group.key === selectedKey;
            const bestRun = bestByMetric(group.runs, "sharpe");
            return (
              <button
                key={group.key}
                type="button"
                onClick={() => onSelect(group.key)}
                className={`w-full rounded-lg border p-3 text-left ${
                  active
                    ? "border-teal-200 bg-teal-50 text-teal-950 dark:border-teal-400/30 dark:bg-teal-950/30 dark:text-teal-100"
                    : "border-transparent bg-white text-zinc-700 hover:border-zinc-200 hover:bg-zinc-50 dark:bg-transparent dark:text-slate-300 dark:hover:border-slate-700 dark:hover:bg-slate-900/70"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="font-semibold">{group.label}</div>
                  <span className="rounded border border-zinc-200 bg-white px-2 py-1 text-[11px] text-zinc-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
                    {group.category}
                  </span>
                </div>
                <div className="mt-2 line-clamp-2 text-xs leading-5 text-zinc-500 dark:text-slate-500">{group.description || "从 RunRegistry 聚合出来的策略族"}</div>
                <div className="mt-3 grid grid-cols-3 gap-2 text-[11px]">
                  <div>
                    <div className="text-zinc-400">Runs</div>
                    <div className="font-mono font-semibold tabular-nums">{formatNumber(group.runs.length, "0")}</div>
                  </div>
                  <div>
                    <div className="text-zinc-400">Best Sharpe</div>
                    <div className="font-mono font-semibold tabular-nums">{formatMetric(metricOf(bestRun, "sharpe"))}</div>
                  </div>
                  <div>
                    <div className="text-zinc-400">Variants</div>
                    <div className="font-mono font-semibold tabular-nums">{formatNumber(group.variants.length, "0")}</div>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </section>
    </aside>
  );
}

function SummaryCard({ label, value, hint, tone = "" }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-slate-800 dark:bg-slate-900/70">
      <div className="text-[11px] text-zinc-500 dark:text-slate-500">{label}</div>
      <div className={`mt-2 font-mono text-lg font-semibold tabular-nums ${tone || "text-zinc-950 dark:text-zinc-100"}`}>{value}</div>
      {hint ? <div className="mt-1 truncate text-[11px] text-zinc-500 dark:text-slate-500">{hint}</div> : null}
    </div>
  );
}

function ResultsHeader({ group }) {
  const bestReturnRun = bestByMetric(group.runs, "cumulative_return");
  const bestSharpeRun = bestByMetric(group.runs, "sharpe");
  const bestExcessRun = bestByMetric(group.runs, "excess_return_vs_buy_hold");

  return (
    <section className="lab-card overflow-hidden p-5">
      <div className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 rounded-full bg-teal-200/30 blur-3xl dark:bg-teal-500/10" />
      <div className="relative flex flex-col gap-5 2xl:flex-row 2xl:items-end 2xl:justify-between">
        <div>
          <div className="inline-flex items-center gap-2 rounded-md border border-teal-200 bg-teal-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-teal-700 dark:border-teal-400/30 dark:bg-teal-950/30 dark:text-teal-200">
            <Flask size={14} />
            Strategy Family
          </div>
          <h2 className="mt-4 text-4xl font-semibold tracking-[-0.06em] text-zinc-950 dark:text-zinc-100">{group.label}</h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-600 dark:text-slate-400">
            {group.description || "按策略族聚合所有 workflow_run。这里展示参数版本、回测窗口、收益风险指标和 BTC 买入持有基线。"}
          </p>
        </div>
        <div className="grid min-w-[520px] gap-3 sm:grid-cols-4">
          <SummaryCard label="回测次数" value={formatNumber(group.runs.length, "0")} hint={`${formatNumber(group.variants.length, "0")} 个参数版本`} />
          <SummaryCard label="最高收益" value={formatPercent(metricOf(bestReturnRun, "cumulative_return"))} hint={bestReturnRun ? parameterSummary(bestReturnRun) : ""} tone="text-emerald-700 dark:text-emerald-300" />
          <SummaryCard label="最佳 Sharpe" value={formatMetric(metricOf(bestSharpeRun, "sharpe"))} hint={bestSharpeRun ? runWindow(bestSharpeRun) : ""} />
          <SummaryCard label="最佳超额" value={formatPercent(metricOf(bestExcessRun, "excess_return_vs_buy_hold"))} hint="vs BTC 持有" tone="text-emerald-700 dark:text-emerald-300" />
        </div>
      </div>
    </section>
  );
}

function MetricCell({ run, column }) {
  const value = valueFor(run, column.key);
  return (
    <td className={`whitespace-nowrap px-3 py-4 text-right font-mono text-xs tabular-nums ${column.strong ? "font-semibold" : ""} ${toneFor(value, column)}`}>
      {formatValue(value, column.kind)}
    </td>
  );
}

function RunDetailRow({ run, colSpan }) {
  const params = strategyParamsOf(run);
  const execution = run.execution_assumptions || {};
  const attribution = run.backtest_attribution || {};

  return (
    <tr className="border-t border-teal-100 bg-teal-50/40 dark:border-teal-400/20 dark:bg-teal-950/10">
      <td colSpan={colSpan} className="px-4 py-4">
        <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr_0.9fr]">
          <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950/50">
            <div className="flex items-center gap-2 text-sm font-semibold text-zinc-950 dark:text-zinc-100">
              <Scales size={17} />
              策略参数
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              {Object.entries(params).length ? (
                Object.entries(params).map(([key, value]) => (
                  <div key={key}>
                    <div className="text-[11px] text-zinc-500 dark:text-slate-500">{parameterLabels[key] || key}</div>
                    <div className="mt-1 font-mono text-xs text-zinc-900 dark:text-slate-100">{String(value)}</div>
                  </div>
                ))
              ) : (
                <div className="text-xs text-zinc-500 dark:text-slate-500">manifest 中没有结构化参数。</div>
              )}
            </div>
          </div>

          <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950/50">
            <div className="flex items-center gap-2 text-sm font-semibold text-zinc-950 dark:text-zinc-100">
              <ChartLineUp size={17} />
              回测设定
            </div>
            <div className="mt-3 grid gap-3 text-xs">
              <div>
                <div className="text-zinc-500 dark:text-slate-500">标的 / 周期</div>
                <div className="mt-1 font-mono text-zinc-900 dark:text-slate-100">{(run.symbols || []).join(" / ") || "-"} · {run.timeframe || "-"}</div>
              </div>
              <div>
                <div className="text-zinc-500 dark:text-slate-500">费用 / 滑点</div>
                <div className="mt-1 font-mono text-zinc-900 dark:text-slate-100">{execution.fee_bps ?? "-"} bps / {execution.slippage_bps ?? "-"} bps</div>
              </div>
              <div>
                <div className="text-zinc-500 dark:text-slate-500">Manifest</div>
                <div className="mt-1 break-all font-mono text-zinc-900 dark:text-slate-100">{run.manifest_path}</div>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950/50">
            <div className="flex items-center gap-2 text-sm font-semibold text-zinc-950 dark:text-zinc-100">
              <TrendUp size={17} />
              成本归因
            </div>
            <div className="mt-3 grid gap-3 text-xs">
              <div>
                <div className="text-zinc-500 dark:text-slate-500">Gross return sum</div>
                <div className="mt-1 font-mono text-zinc-900 dark:text-slate-100">{formatMetric(attribution.gross_return_sum)}</div>
              </div>
              <div>
                <div className="text-zinc-500 dark:text-slate-500">Trading cost sum</div>
                <div className="mt-1 font-mono text-zinc-900 dark:text-slate-100">{formatMetric(attribution.trading_cost_sum)}</div>
              </div>
              <div>
                <div className="text-zinc-500 dark:text-slate-500">Funding cost sum</div>
                <div className="mt-1 font-mono text-zinc-900 dark:text-slate-100">{formatMetric(attribution.funding_cost_sum)}</div>
              </div>
            </div>
          </div>
        </div>
      </td>
    </tr>
  );
}

function ResultsMatrix({ runs, expandedId, onExpand }) {
  const colSpan = 4 + metricColumns.length;

  if (!runs.length) {
    return (
      <section className="lab-card p-5">
        <div className="flex items-center gap-2 text-sm font-semibold text-zinc-950 dark:text-zinc-100">
          <ListChecks size={18} />
          回测结果矩阵
        </div>
        <div className="mt-4 rounded-lg border border-dashed border-zinc-300 bg-zinc-50 p-6 text-sm text-zinc-500 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-400">
          还没有回测记录。用 Cursor/Codex/CLI 跑完 workflow 后，RunRegistry 会出现在这里。
        </div>
      </section>
    );
  }

  return (
    <section className="lab-card overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-200 px-4 py-3 dark:border-slate-800">
        <div className="flex items-center gap-2 text-sm font-semibold text-zinc-950 dark:text-zinc-100">
          <ListChecks size={18} />
          回测结果矩阵
        </div>
        <div className="text-xs text-zinc-500 dark:text-slate-500">{formatNumber(runs.length, "0")} 条 Run · 点击行展开参数和归因</div>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-[1780px] text-left text-sm">
          <thead className="border-b border-zinc-200 bg-zinc-50 text-[11px] uppercase tracking-[0.12em] text-zinc-500 dark:border-slate-800 dark:bg-slate-900/70 dark:text-slate-500">
            <tr>
              <th className="w-[210px] px-4 py-3 font-semibold">参数版本</th>
              <th className="w-[230px] px-3 py-3 font-semibold">参数摘要</th>
              <th className="w-[110px] px-3 py-3 font-semibold">窗口</th>
              <th className="w-[130px] px-3 py-3 font-semibold">运行时间</th>
              {metricColumns.map((column) => (
                <th key={column.key} className="whitespace-nowrap px-3 py-3 text-right font-semibold">{column.label}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100 dark:divide-slate-800">
            {runs.map((run) => {
              const id = runIdentity(run);
              const expanded = id === expandedId;
              return (
                <Fragment key={id}>
                  <tr
                    onClick={() => onExpand(expanded ? "" : id)}
                    className={`cursor-pointer align-top ${expanded ? "bg-teal-50/70 dark:bg-teal-950/20" : "hover:bg-zinc-50 dark:hover:bg-slate-900/50"}`}
                  >
                    <td className="px-4 py-4">
                      <div className="font-mono text-xs font-semibold text-zinc-950 dark:text-zinc-100">{runVariantId(run)}</div>
                      <div className="mt-1 text-[11px] text-zinc-500 dark:text-slate-500">{shortHash(run.run_id)}</div>
                    </td>
                    <td className="px-3 py-4">
                      <div className="text-xs font-medium text-zinc-800 dark:text-slate-200">{parameterSummary(run)}</div>
                      <div className="mt-1 text-[11px] text-zinc-500 dark:text-slate-500">{run.strategy_name || run.name}</div>
                    </td>
                    <td className="whitespace-nowrap px-3 py-4 text-xs text-zinc-700 dark:text-slate-300">{runWindow(run)}</td>
                    <td className="whitespace-nowrap px-3 py-4 font-mono text-xs text-zinc-500 dark:text-slate-500">{formatDate(run.generated_at)}</td>
                    {metricColumns.map((column) => (
                      <MetricCell key={column.key} run={run} column={column} />
                    ))}
                  </tr>
                  {expanded ? <RunDetailRow run={run} colSpan={colSpan} /> : null}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function StrategyLabClient({ initialTemplates = [], initialRuns = [] }) {
  const searchParams = useSearchParams();
  const [selectedKey, setSelectedKey] = useState(() => strategyKeyFromTemplate(initialTemplates[0]));
  const [expandedId, setExpandedId] = useState("");

  const groups = useMemo(() => buildStrategyGroups(initialTemplates, initialRuns), [initialTemplates, initialRuns]);
  const selectedGroup = useMemo(() => groups.find((group) => group.key === selectedKey) ?? groups[0] ?? null, [groups, selectedKey]);

  useEffect(() => {
    const requestedStrategy = searchParams.get("strategy");
    if (requestedStrategy && groups.some((group) => group.key === requestedStrategy)) {
      setSelectedKey(requestedStrategy);
      return;
    }
    if (!groups.some((group) => group.key === selectedKey) && groups[0]) {
      setSelectedKey(groups[0].key);
    }
  }, [groups, searchParams, selectedKey]);

  useEffect(() => {
    const requestedRun = searchParams.get("run");
    if (requestedRun) {
      setExpandedId(requestedRun);
      return;
    }
    setExpandedId("");
  }, [searchParams, selectedGroup?.key]);

  return (
    <div className="grid gap-5 xl:grid-cols-[360px_1fr]">
      <StrategyRail groups={groups} selectedKey={selectedGroup?.key ?? selectedKey} onSelect={setSelectedKey} />

      {selectedGroup ? (
        <div className="space-y-5">
          <ResultsHeader group={selectedGroup} />
          <ResultsMatrix
            runs={selectedGroup.runs}
            expandedId={expandedId}
            onExpand={setExpandedId}
          />
        </div>
      ) : (
        <section className="rounded-lg border border-dashed border-zinc-300 bg-white p-8 text-zinc-500 dark:border-slate-700 dark:bg-[#111722]">
          暂无回测记录，请先用 IDE/CLI 运行策略 workflow。
        </section>
      )}
    </div>
  );
}
