"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

import { fetchStrategyLabAppJson, STRATEGY_LAB_ENDPOINTS } from "../lib/strategy-lab-api";
import {
  buildLabRunHref,
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
  strategyLabel,
} from "../lib/strategy-workbench";

export const BACKTEST_PAGE_SIZE = 30;

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

function buildRunsSearchParams(offset) {
  return new URLSearchParams({
    kind: "workflow_run",
    limit: String(BACKTEST_PAGE_SIZE + 1),
    offset: String(offset),
    sort_by: "generated_at",
    sort_order: "desc",
  });
}

function valueFor(run, key) {
  if (key === "fee_ratio") {
    return costRatioOf(run);
  }
  return metricOf(run, key);
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

function formatValue(value, kind) {
  return kind === "percent" ? formatPercent(value) : formatMetric(value);
}

function MetricCell({ run, column }) {
  const value = valueFor(run, column.key);
  return (
    <td className={`whitespace-nowrap px-3 py-4 text-right font-mono text-xs tabular-nums ${column.strong ? "font-semibold" : ""} ${toneFor(value, column)}`}>
      {formatValue(value, column.kind)}
    </td>
  );
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
    <div className="overflow-hidden rounded-[1rem] border border-zinc-200 bg-white shadow-[0_18px_50px_-42px_rgba(15,23,42,0.45)] dark:border-slate-800 dark:bg-[#111722]">
      <div className="overflow-x-auto">
        <table className="min-w-[1840px] text-left text-sm">
          <thead className="border-b border-zinc-200 bg-zinc-50 text-[11px] uppercase tracking-[0.14em] text-zinc-500 dark:border-slate-800 dark:bg-slate-900/70 dark:text-slate-500">
            <tr>
              <th className="w-[170px] whitespace-nowrap px-4 py-3 font-semibold">策略</th>
              <th className="w-[210px] whitespace-nowrap px-3 py-3 font-semibold">参数版本</th>
              <th className="w-[230px] whitespace-nowrap px-3 py-3 font-semibold">参数摘要</th>
              <th className="w-[110px] whitespace-nowrap px-3 py-3 font-semibold">窗口</th>
              <th className="w-[130px] whitespace-nowrap px-3 py-3 font-semibold">运行时间</th>
              {metricColumns.map((column) => (
                <th key={column.key} className="whitespace-nowrap px-3 py-3 text-right font-semibold">{column.label}</th>
              ))}
              <th className="w-[130px] whitespace-nowrap px-4 py-3 text-right font-semibold">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100 dark:divide-slate-800">
            {records.map((run) => (
              <tr key={runIdentity(run)} className="align-top hover:bg-blue-50/40 dark:hover:bg-slate-900/50">
                <td className="px-4 py-4">
                  <div className="font-semibold text-zinc-950 dark:text-zinc-100">{strategyLabel(run)}</div>
                  <div className="mt-1 text-[11px] text-zinc-500 dark:text-slate-500">{run.strategy_type || run.signal_name || "-"}</div>
                </td>
                <td className="px-3 py-4">
                  <div className="font-mono text-xs font-semibold text-zinc-950 dark:text-zinc-100">{runVariantId(run)}</div>
                  <div className="mt-1 text-[11px] text-zinc-500 dark:text-slate-500">{shortHash(run.run_id)}</div>
                </td>
                <td className="px-3 py-4">
                  <div className="text-xs font-medium text-zinc-800 dark:text-slate-200">{parameterSummary(run)}</div>
                  <div className="mt-1 truncate text-[11px] text-zinc-500 dark:text-slate-500">{run.name}</div>
                </td>
                <td className="whitespace-nowrap px-3 py-4 text-xs text-zinc-700 dark:text-slate-300">{runWindow(run)}</td>
                <td className="whitespace-nowrap px-3 py-4 font-mono text-xs text-zinc-500 dark:text-slate-500">{formatDate(run.generated_at)}</td>
                {metricColumns.map((column) => (
                  <MetricCell key={column.key} run={run} column={column} />
                ))}
                <td className="px-4 py-4 text-right">
                  <Link
                    href={buildLabRunHref(run)}
                    className="inline-flex rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-700 hover:-translate-y-0.5 hover:bg-blue-100"
                  >
                    打开策略
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function BacktestsClient({ initialRecords = [], initialHasMore = false }) {
  const [records, setRecords] = useState(initialRecords);
  const [hasMore, setHasMore] = useState(initialHasMore);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const loadMoreRef = useRef(null);

  const loadMore = useCallback(async () => {
    if (loading || !hasMore) {
      return;
    }
    setLoading(true);
    setError("");
    try {
      const payload = await fetchStrategyLabAppJson(STRATEGY_LAB_ENDPOINTS.runs, {
        searchParams: buildRunsSearchParams(records.length),
      });
      const nextRows = payload.runs ?? [];
      setRecords((current) => [...current, ...nextRows.slice(0, BACKTEST_PAGE_SIZE)]);
      setHasMore(nextRows.length > BACKTEST_PAGE_SIZE);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "加载更多回测记录失败");
    } finally {
      setLoading(false);
    }
  }, [hasMore, loading, records.length]);

  useEffect(() => {
    const target = loadMoreRef.current;
    if (!target || !hasMore) {
      return undefined;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          loadMore();
        }
      },
      { rootMargin: "360px 0px" },
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [hasMore, loadMore]);

  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold text-zinc-950">全部回测记录</h2>
      <BacktestTable records={records} />
      <div ref={loadMoreRef} className="min-h-10 text-center text-xs text-zinc-500">
        {loading ? "正在加载更多回测记录..." : null}
        {!loading && error ? (
          <button type="button" onClick={loadMore} className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-700">
            {error}，点击重试
          </button>
        ) : null}
        {!loading && !error && hasMore ? "继续上滑自动加载更多" : null}
        {!loading && !error && !hasMore && records.length > 0 ? "已加载全部回测记录" : null}
      </div>
    </section>
  );
}
