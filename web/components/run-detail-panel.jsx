"use client";

import { useEffect, useMemo, useState } from "react";
import { ChartLineUp, Crosshair, GitBranch, Pulse, WarningCircle } from "@phosphor-icons/react";

import { fetchStrategyLabAppJson, STRATEGY_LAB_ENDPOINTS } from "../lib/strategy-lab-api";
import { formatMetric, formatNumber, formatPercent, metricOf, runIdentity, shortHash } from "../lib/strategy-workbench";

function endpointForRun(run) {
  if (run?.kind === "experiment_run") {
    return STRATEGY_LAB_ENDPOINTS.experimentDetail;
  }
  if (run?.kind === "comparison_run") {
    return STRATEGY_LAB_ENDPOINTS.comparisonDetail;
  }
  return STRATEGY_LAB_ENDPOINTS.runDetail;
}

function useRunDetail(run) {
  const [state, setState] = useState({ loading: false, error: "", detail: null });

  useEffect(() => {
    if (!run?.manifest_path) {
      setState({ loading: false, error: "", detail: null });
      return undefined;
    }

    let cancelled = false;
    setState({ loading: true, error: "", detail: null });
    fetchStrategyLabAppJson(endpointForRun(run), {
      searchParams: new URLSearchParams({
        manifest_path: run.manifest_path,
      }),
    })
      .then((detail) => {
        if (!cancelled) {
          setState({ loading: false, error: "", detail });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setState({ loading: false, error: error instanceof Error ? error.message : "加载 Run 详情失败", detail: null });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [run?.kind, run?.manifest_path]);

  return state;
}

function Stat({ label, value, tone = "neutral" }) {
  const toneClass = tone === "good" ? "text-emerald-700" : tone === "bad" ? "text-rose-700" : "text-zinc-950 dark:text-zinc-100";
  return (
    <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-slate-800 dark:bg-slate-900/70">
      <div className="text-[11px] font-semibold tracking-[0.12em] text-zinc-500 dark:text-slate-500">{label}</div>
      <div className={`mt-2 font-mono text-xl font-semibold tabular-nums ${toneClass}`}>{value}</div>
    </div>
  );
}

function LineChart({ rows, yKey = "equity" }) {
  const points = useMemo(() => {
    const values = (Array.isArray(rows) ? rows : [])
      .map((row, index) => ({ index, value: Number(row?.[yKey]) }))
      .filter((point) => Number.isFinite(point.value));

    if (values.length < 2) {
      return "";
    }

    const min = Math.min(...values.map((point) => point.value));
    const max = Math.max(...values.map((point) => point.value));
    const spread = max - min || 1;
    const width = 600;
    const height = 160;
    return values
      .map((point, index) => {
        const x = (index / (values.length - 1)) * width;
        const y = height - ((point.value - min) / spread) * height;
        return `${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(" ");
  }, [rows, yKey]);

  if (!points) {
    return (
      <div className="grid h-[190px] place-items-center rounded-xl border border-dashed border-zinc-300 bg-zinc-50 text-xs text-zinc-500 dark:border-slate-700 dark:bg-slate-900/60">
        暂无结构化权益曲线
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-3 dark:border-slate-800 dark:bg-slate-900/70">
      <svg viewBox="0 0 600 160" role="img" aria-label="权益曲线" className="h-[190px] w-full overflow-visible">
        <polyline fill="none" stroke="rgba(20, 184, 166, 0.95)" strokeLinecap="round" strokeLinejoin="round" strokeWidth="4" points={points} />
      </svg>
    </div>
  );
}

function Field({ label, value }) {
  return (
    <div>
      <div className="text-zinc-500 dark:text-slate-500">{label}</div>
      <div className="mt-1 break-all font-mono text-zinc-900 dark:text-slate-100">{value || "-"}</div>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <section className="rounded-xl border border-zinc-200 bg-white p-5 shadow-[0_18px_50px_-44px_rgba(15,23,42,0.35)] dark:border-slate-800 dark:bg-[#111722]">
      <div className="h-4 w-32 animate-pulse rounded-full bg-zinc-200 dark:bg-slate-800" />
      <div className="mt-4 grid gap-3 sm:grid-cols-4">
        <div className="h-20 animate-pulse rounded-lg bg-zinc-100 dark:bg-slate-800" />
        <div className="h-20 animate-pulse rounded-lg bg-zinc-100 dark:bg-slate-800" />
        <div className="h-20 animate-pulse rounded-lg bg-zinc-100 dark:bg-slate-800" />
        <div className="h-20 animate-pulse rounded-lg bg-zinc-100 dark:bg-slate-800" />
      </div>
      <div className="mt-4 h-48 animate-pulse rounded-xl bg-zinc-100 dark:bg-slate-800" />
    </section>
  );
}

export default function RunDetailPanel({ run, detailState: externalDetailState, candidate = false, onPromoteCandidate }) {
  const fetchedDetailState = useRunDetail(externalDetailState ? null : run);
  const detailState = externalDetailState ?? fetchedDetailState;

  if (!run) {
    return (
      <section className="rounded-xl border border-dashed border-zinc-300 bg-white p-8 text-sm text-zinc-500 dark:border-slate-700 dark:bg-[#111722]">
        选择一条回测记录后，会在这里展示指标、权益曲线、运行指纹和模拟盘摘要。
      </section>
    );
  }

  if (detailState.loading) {
    return <DetailSkeleton />;
  }

  if (detailState.error) {
    return (
      <section className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700 dark:border-rose-400/30 dark:bg-rose-950/20 dark:text-rose-200">
        <div className="flex items-center gap-2 font-semibold">
          <WarningCircle size={18} />
          详情加载失败
        </div>
        <div className="mt-2 break-all">{detailState.error}</div>
      </section>
    );
  }

  const detail = detailState.detail;
  const metrics = detail?.metrics?.backtest_metrics ?? run.backtest_metrics ?? {};
  const attribution = detail?.metrics?.backtest_attribution ?? run.backtest_attribution ?? {};
  const paperSummary = run.paper_summary ?? {};
  const trades = detail?.artifacts?.trades ?? [];
  const equityCurve = detail?.artifacts?.equity_curve ?? [];
  const hasPaper = run.paper_report_path || Object.keys(paperSummary).length > 0;

  return (
    <section className="space-y-4 rounded-xl border border-zinc-200 bg-white p-5 shadow-[0_18px_50px_-44px_rgba(15,23,42,0.35)] dark:border-slate-800 dark:bg-[#111722]">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-zinc-500 dark:text-slate-500">
            <Crosshair size={15} />
            Selected Run
          </div>
          <h2 className="mt-2 max-w-3xl text-xl font-semibold tracking-[-0.03em] text-zinc-950 dark:text-zinc-100">{run.strategy_name || run.name}</h2>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-zinc-500 dark:text-slate-400">
            <span className="rounded border border-zinc-200 px-2 py-1 font-mono dark:border-slate-700">{shortHash(run.run_id)}</span>
            <span className="rounded border border-zinc-200 px-2 py-1 dark:border-slate-700">{hasPaper ? "含模拟盘摘要" : "仅回测"}</span>
            {candidate ? <span className="rounded border border-emerald-200 bg-emerald-50 px-2 py-1 text-emerald-700 dark:border-emerald-400/30 dark:bg-emerald-950/30 dark:text-emerald-200">当前候选</span> : null}
          </div>
        </div>
        {onPromoteCandidate ? (
          <button
            type="button"
            onClick={() => onPromoteCandidate(run)}
            className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-800 hover:-translate-y-0.5 hover:bg-emerald-100 dark:border-emerald-400/30 dark:bg-emerald-950/30 dark:text-emerald-200"
          >
            {candidate ? "已设为候选" : "设为模拟盘候选"}
          </button>
        ) : null}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Sharpe" value={formatMetric(metrics.sharpe ?? metricOf(run, "sharpe"))} tone={(metrics.sharpe ?? metricOf(run, "sharpe")) > 0 ? "good" : "bad"} />
        <Stat label="累计收益" value={formatPercent(metrics.cumulative_return ?? metricOf(run, "cumulative_return"))} tone={(metrics.cumulative_return ?? metricOf(run, "cumulative_return")) > 0 ? "good" : "bad"} />
        <Stat label="最大回撤" value={formatPercent(metrics.max_drawdown ?? metricOf(run, "max_drawdown"))} tone="bad" />
        <Stat label="换手" value={formatMetric(metrics.avg_turnover ?? metricOf(run, "avg_turnover"))} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <div>
          <div className="mb-3 flex items-center gap-2">
            <ChartLineUp size={18} className="text-teal-700 dark:text-teal-300" />
            <div>
              <div className="text-sm font-semibold text-zinc-950 dark:text-zinc-100">权益曲线</div>
              <div className="text-xs text-zinc-500 dark:text-slate-500">{equityCurve.length ? `${formatNumber(equityCurve.length, "0")} 个点` : "等待 run-detail 返回 artifact"}</div>
            </div>
          </div>
          <LineChart rows={equityCurve} />
        </div>

        <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 text-xs dark:border-slate-800 dark:bg-slate-900/70">
          <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-zinc-950 dark:text-zinc-100">
            <GitBranch size={17} />
            运行指纹
          </div>
          <div className="space-y-3">
            <Field label="Config hash" value={run.config_hash} />
            <Field label="Data snapshot" value={run.data_snapshot_id} />
            <Field label="Manifest" value={runIdentity(run)} />
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 text-xs dark:border-slate-800 dark:bg-slate-900/70">
          <div className="text-sm font-semibold text-zinc-950 dark:text-zinc-100">回测归因</div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <Field label="Gross return sum" value={formatMetric(attribution.gross_return_sum)} />
            <Field label="Trading cost sum" value={formatMetric(attribution.trading_cost_sum)} />
            <Field label="Funding cost sum" value={formatMetric(attribution.funding_cost_sum)} />
            <Field label="Trade rows" value={formatNumber(trades.length, "0")} />
            <Field label="Top symbol" value={attribution.top_symbol} />
            <Field label="Worst symbol" value={attribution.worst_symbol} />
          </div>
        </div>

        <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 text-xs dark:border-slate-800 dark:bg-slate-900/70">
          <div className="flex items-center gap-2 text-sm font-semibold text-zinc-950 dark:text-zinc-100">
            <Pulse size={17} />
            模拟盘摘要
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <Field label="Final equity" value={formatMetric(paperSummary.final_equity)} />
            <Field label="Fill count" value={formatNumber(paperSummary.fill_count, "0")} />
            <Field label="Funding cashflow" value={formatMetric(paperSummary.funding_cashflow)} />
            <Field label="Paper report" value={run.paper_report_path} />
          </div>
        </div>
      </div>
    </section>
  );
}
