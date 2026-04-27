"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  ChartLineUp,
  Crosshair,
  Database,
  GitBranch,
  ListChecks,
  Trophy,
} from "@phosphor-icons/react";

import { fetchStrategyLabAppJson, STRATEGY_LAB_ENDPOINTS } from "../lib/strategy-lab-api";

const numberFormat = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 4,
});

function fmt(value, fallback = "-") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return fallback;
  }
  return numberFormat.format(Number(value));
}

function pct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return `${(Number(value) * 100).toFixed(2)}%`;
}

function metricOf(run, key) {
  return run?.backtest_metrics?.[key] ?? 0;
}

function runTypeLabel(run) {
  return run?.variant_id || run?.strategy_type || run?.signal_type || "-";
}

function metricLabel(key) {
  const labels = {
    sharpe: "Sharpe",
    cumulative_return: "Cumulative",
    annualized_return: "Annualized",
    max_drawdown: "Max DD",
    avg_turnover: "Turnover",
    final_equity: "Final equity",
  };
  return labels[key] || key;
}

function isPercentMetric(key) {
  return ["cumulative_return", "annualized_return", "max_drawdown"].includes(key);
}

function formatMetricValue(value, key) {
  return isPercentMetric(key) ? pct(value) : fmt(value);
}

const fieldClassName = "dashboard-field";
const primaryButtonClassName = "dashboard-button-primary";
const secondaryButtonClassName = "dashboard-button-secondary";
const panelLabelClassName = "text-[11px] font-semibold uppercase tracking-[0.16em] text-zinc-500";

function compareRunsByMetric(left, right, key, direction = "max") {
  const leftValue = Number(metricOf(left, key));
  const rightValue = Number(metricOf(right, key));
  const normalizedLeft = Number.isFinite(leftValue) ? leftValue : direction === "min" ? Number.POSITIVE_INFINITY : Number.NEGATIVE_INFINITY;
  const normalizedRight = Number.isFinite(rightValue) ? rightValue : direction === "min" ? Number.POSITIVE_INFINITY : Number.NEGATIVE_INFINITY;
  if (direction === "min") {
    return normalizedLeft - normalizedRight;
  }
  return normalizedRight - normalizedLeft;
}

function buildRunsSearchParams(query = {}) {
  const searchParams = new URLSearchParams();
  if (query.search) {
    searchParams.set("search", query.search);
  }
  if (query.strategyType) {
    searchParams.set("strategy_type", query.strategyType);
  }
  if (query.sortBy) {
    searchParams.set("sort_by", query.sortBy);
  }
  if (query.sortOrder) {
    searchParams.set("sort_order", query.sortOrder);
  }
  searchParams.set("limit", String(query.limit ?? 200));
  return searchParams;
}

function pickBestWorkflowRun(runs) {
  const workflowRuns = runs.filter((run) => run.kind === "workflow_run");
  if (workflowRuns.length === 0) {
    return null;
  }
  return [...workflowRuns].sort((a, b) => metricOf(b, "sharpe") - metricOf(a, "sharpe"))[0];
}

function pickInitialRun(runs) {
  const bestWorkflow = pickBestWorkflowRun(runs);
  if (bestWorkflow) {
    return bestWorkflow;
  }
  return runs.find((run) => ["experiment_run", "comparison_run"].includes(run.kind)) ?? null;
}

function useRuns(initialRuns = [], initialError = "") {
  const [state, setState] = useState({
    loading: false,
    error: initialError,
    runs: initialRuns,
  });

  const reload = useCallback(async (query = {}) => {
    setState((current) => ({
      ...current,
      loading: true,
      error: "",
    }));
    try {
      const data = await fetchStrategyLabAppJson(STRATEGY_LAB_ENDPOINTS.runs, {
        searchParams: buildRunsSearchParams(query),
      });
      setState({
        loading: false,
        error: "",
        runs: data.runs ?? [],
      });
    } catch (error) {
      setState((current) => ({
        loading: false,
        error: error.message,
        runs: current.runs,
      }));
    }
  }, []);

  return {
    ...state,
    reload,
  };
}

function useSelectedDetail(run) {
  const [state, setState] = useState({ loading: false, error: "", detail: null });

  useEffect(() => {
    if (!run?.manifest_path) {
      setState({ loading: false, error: "", detail: null });
      return;
    }

    const endpoint =
      run.kind === "workflow_run"
        ? STRATEGY_LAB_ENDPOINTS.runDetail
        : run.kind === "experiment_run"
          ? STRATEGY_LAB_ENDPOINTS.experimentDetail
          : run.kind === "comparison_run"
            ? STRATEGY_LAB_ENDPOINTS.comparisonDetail
            : null;
    if (!endpoint) {
      setState({ loading: false, error: "", detail: null });
      return;
    }

    let cancelled = false;
    setState({ loading: true, error: "", detail: null });
    fetchStrategyLabAppJson(endpoint, {
      searchParams: new URLSearchParams({
        manifest_path: run.manifest_path,
      }),
    })
      .then((data) => {
        if (!cancelled) {
          setState({ loading: false, error: "", detail: data });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setState({ loading: false, error: error.message, detail: null });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [run?.kind, run?.manifest_path]);

  return state;
}

function Card({ children, className = "" }) {
  return (
    <section
      className={`dashboard-card ${className}`}
    >
      {children}
    </section>
  );
}

function Skeleton() {
  return (
    <div className="space-y-4 p-6">
      <div className="h-3 w-28 animate-pulse rounded-full bg-zinc-200/80" />
      <div className="h-10 w-3/4 animate-pulse rounded-[1.2rem] bg-zinc-200/70" />
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="h-24 animate-pulse rounded-[1.25rem] bg-zinc-100" />
        <div className="h-24 animate-pulse rounded-[1.25rem] bg-zinc-100" />
        <div className="h-24 animate-pulse rounded-[1.25rem] bg-zinc-100" />
      </div>
      <div className="h-40 animate-pulse rounded-[1.5rem] bg-zinc-100" />
      <div className="h-4 w-2/3 animate-pulse rounded-full bg-zinc-200/80" />
    </div>
  );
}

function EmptyState() {
  return (
    <div className="grid min-h-[520px] gap-5 rounded-[2rem] border border-dashed border-zinc-300/80 bg-white/70 p-8 lg:grid-cols-[0.95fr_0.75fr] lg:items-end">
      <div className="flex flex-col justify-between gap-10">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-zinc-200 bg-white px-3 py-1 text-[11px] tracking-[0.16em] text-zinc-500">
            <Database size={14} />
            Results center
          </div>
          <h2 className="mt-5 max-w-xl text-4xl font-semibold tracking-[-0.04em] text-zinc-950 md:text-5xl">
            还没有可展示的运行结果
          </h2>
          <p className="mt-4 max-w-[58ch] text-sm leading-7 text-zinc-600">
            先跑一条策略、一次实验，或者导入已有回测记录。面板会自动读取结果索引，展示排序、批次关系、权益曲线和交易轨迹。
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-[1.5rem] border border-zinc-200 bg-white px-4 py-4">
            <div className="text-xs tracking-[0.14em] text-zinc-500">1</div>
            <div className="mt-2 text-sm font-medium text-zinc-950">运行 workflow</div>
            <div className="mt-1 text-xs leading-6 text-zinc-500">写入回测记录、指标和工件引用</div>
          </div>
          <div className="rounded-[1.5rem] border border-zinc-200 bg-white px-4 py-4">
            <div className="text-xs tracking-[0.14em] text-zinc-500">2</div>
            <div className="mt-2 text-sm font-medium text-zinc-950">生成 experiment</div>
            <div className="mt-1 text-xs leading-6 text-zinc-500">批量变体、自动选优和子运行关系会一起入库</div>
          </div>
          <div className="rounded-[1.5rem] border border-zinc-200 bg-white px-4 py-4">
            <div className="text-xs tracking-[0.14em] text-zinc-500">3</div>
            <div className="mt-2 text-sm font-medium text-zinc-950">在 dashboard 下钻</div>
            <div className="mt-1 text-xs leading-6 text-zinc-500">从批次到单条策略，一路查看指标和明细</div>
          </div>
        </div>
      </div>
      <div className="rounded-[1.8rem] border border-zinc-200 bg-zinc-50 p-5 text-zinc-950 shadow-[0_24px_60px_-42px_rgba(37,61,56,0.28)]">
        <div className="text-xs tracking-[0.16em] text-zinc-500">Waiting for first run</div>
        <div className="mt-5 space-y-3">
          <div className="h-14 animate-pulse rounded-[1.2rem] bg-zinc-200/80" />
          <div className="h-14 animate-pulse rounded-[1.2rem] bg-zinc-200/80" />
          <div className="h-36 animate-pulse rounded-[1.4rem] bg-zinc-200/80" />
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, tone = "neutral" }) {
  const color = tone === "good" ? "text-teal-700" : tone === "bad" ? "text-rose-700" : "text-zinc-950";

  return (
    <div className="rounded-[1.2rem] bg-[#f5f7f2] px-4 py-4 shadow-[inset_0_0_0_1px_rgba(24,24,27,0.05)]">
      <div className={panelLabelClassName}>{label}</div>
      <div className={`mt-2 font-mono text-2xl font-semibold tracking-[-0.03em] tabular-nums ${color}`}>{value}</div>
    </div>
  );
}

function OverviewDeck({ runs, selected }) {
  const workflowRuns = runs.filter((run) => run.kind === "workflow_run");
  const experimentRuns = runs.filter((run) => run.kind === "experiment_run");
  const comparisonRuns = runs.filter((run) => run.kind === "comparison_run");
  const bestSharpeRun = workflowRuns.length
    ? [...workflowRuns].sort((left, right) => compareRunsByMetric(left, right, "sharpe", "max"))[0]
    : null;

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Card className="border-zinc-200 bg-white bg-none p-5 text-zinc-950 shadow-none">
        <div className="text-[11px] font-semibold tracking-[0.16em] text-zinc-400">Workflow runs</div>
        <div className="mt-3 font-mono text-3xl font-semibold tracking-[-0.05em] text-zinc-950 tabular-nums">{workflowRuns.length}</div>
        <div className="mt-2 text-xs leading-5 text-zinc-400">当前结果库中的可下钻回测记录</div>
      </Card>
      <Card className="border-zinc-200 bg-white bg-none p-5 text-zinc-950 shadow-none">
        <div className="text-[11px] font-semibold tracking-[0.16em] text-zinc-400">Experiment runs</div>
        <div className="mt-3 font-mono text-3xl font-semibold tracking-[-0.05em] text-zinc-950 tabular-nums">{experimentRuns.length}</div>
        <div className="mt-2 text-xs leading-5 text-zinc-400">批量实验、变体和 winner 记录</div>
      </Card>
      <Card className="border-zinc-200 bg-white bg-none p-5 text-zinc-950 shadow-none">
        <div className="text-[11px] font-semibold tracking-[0.16em] text-zinc-400">Comparison runs</div>
        <div className="mt-3 font-mono text-3xl font-semibold tracking-[-0.05em] text-zinc-950 tabular-nums">{comparisonRuns.length}</div>
        <div className="mt-2 text-xs leading-5 text-zinc-400">策略对比批次与子运行关系</div>
      </Card>
      <Card className="border-teal-200/60 bg-[#d8f3ea] bg-none p-5 text-zinc-950 shadow-[0_26px_70px_-42px_rgba(15,118,110,0.52)]">
        <div className="text-[11px] font-semibold tracking-[0.16em] text-teal-800/70">Best sharpe</div>
        <div className="mt-3 text-lg font-semibold tracking-[-0.03em] text-zinc-950">
          {bestSharpeRun?.strategy_name || bestSharpeRun?.name || "No workflow runs"}
        </div>
        <div className="mt-2 font-mono text-3xl font-semibold text-teal-800 tabular-nums">
          {bestSharpeRun ? fmt(metricOf(bestSharpeRun, "sharpe")) : "-"}
        </div>
        <div className="mt-2 text-xs leading-5 text-teal-950/65">
          当前选中: {selected?.strategy_name || selected?.name || "none"}
        </div>
      </Card>
    </div>
  );
}

function Leaderboard({ runs, selected, onSelect }) {
  const workflowRuns = useMemo(
    () =>
      runs
        .filter((run) => run.kind === "workflow_run")
        .sort((a, b) => metricOf(b, "sharpe") - metricOf(a, "sharpe")),
    [runs],
  );

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-zinc-200/70 px-5 py-4">
        <div>
          <div className="text-base font-semibold tracking-[-0.02em] text-zinc-950">策略排行</div>
          <div className="mt-1 text-xs text-zinc-500">当前按 Sharpe 排序，点击切到单条 workflow 明细</div>
        </div>
        <Trophy size={22} className="text-teal-700" weight="duotone" />
      </div>
      <div className="divide-y divide-zinc-100/90">
        {workflowRuns.slice(0, 12).map((run, index) => (
          <button
            key={`${run.run_id}-${run.manifest_path}`}
            type="button"
            onClick={() => onSelect(run)}
            className={`grid w-full grid-cols-[2.2rem_1fr_auto_auto] items-center gap-3 px-5 py-4 text-left transition hover:bg-[#f7fbf7] active:translate-y-px ${
              selected?.manifest_path === run.manifest_path ? "bg-[#e9f7f2] shadow-[inset_3px_0_0_#0f766e]" : ""
            }`}
          >
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-white font-mono text-xs text-zinc-500 shadow-[inset_0_0_0_1px_rgba(24,24,27,0.08)]">
              {String(index + 1).padStart(2, "0")}
            </span>
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold text-zinc-950">{run.strategy_name || run.name}</span>
              <span className="mt-1 block truncate text-xs text-zinc-500">{runTypeLabel(run)}</span>
            </span>
            <span className="text-right text-xs text-zinc-500">
              <span className="block">Sharpe</span>
              <span className="font-mono text-sm font-semibold text-zinc-900 tabular-nums">{fmt(metricOf(run, "sharpe"))}</span>
            </span>
            <span className="text-right text-xs text-zinc-500">
              <span className="block">Return</span>
              <span className="font-mono text-sm font-semibold text-zinc-900 tabular-nums">{pct(metricOf(run, "cumulative_return"))}</span>
            </span>
          </button>
        ))}
      </div>
    </Card>
  );
}

function Experiments({ runs, selected, onSelect }) {
  const experiments = runs.filter((run) => run.kind === "experiment_run").slice(0, 8);

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center gap-2 border-b border-zinc-200/70 px-5 py-4">
        <ListChecks size={20} className="text-zinc-700" />
        <div>
          <div className="text-base font-semibold tracking-[-0.02em] text-zinc-950">实验批次</div>
          <div className="mt-1 text-xs text-zinc-500">包含 sweep 与自动选优结果</div>
        </div>
      </div>
      <div className="divide-y divide-zinc-100">
        {experiments.length === 0 ? (
          <div className="px-5 py-6 text-sm text-zinc-500">暂无 experiment run。</div>
        ) : (
          experiments.map((run) => (
            <button
              key={`${run.run_id}-${run.manifest_path}`}
              type="button"
              onClick={() => onSelect(run)}
              className={`w-full px-5 py-4 text-left transition hover:bg-[#f7fbf7] ${
                selected?.manifest_path === run.manifest_path ? "bg-[#e9f7f2] shadow-[inset_3px_0_0_#0f766e]" : ""
              }`}
            >
              <div className="truncate text-sm font-semibold text-zinc-950">{run.name}</div>
              <div className="mt-1 flex items-center gap-2 text-xs text-zinc-500">
                <span className="font-mono">{run.run_id}</span>
                <span>{run.child_run_count || 0} runs</span>
              </div>
            </button>
          ))
        )}
      </div>
    </Card>
  );
}

function Comparisons({ runs, selected, onSelect }) {
  const comparisons = runs.filter((run) => run.kind === "comparison_run").slice(0, 8);

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center gap-2 border-b border-zinc-200/70 px-5 py-4">
        <GitBranch size={20} className="text-zinc-700" />
        <div>
          <div className="text-base font-semibold tracking-[-0.02em] text-zinc-950">策略对比</div>
          <div className="mt-1 text-xs text-zinc-500">查看对比批次与子运行数量</div>
        </div>
      </div>
      <div className="divide-y divide-zinc-100">
        {comparisons.length === 0 ? (
          <div className="px-5 py-6 text-sm text-zinc-500">暂无 comparison run。</div>
        ) : (
          comparisons.map((run) => (
            <button
              key={`${run.run_id}-${run.manifest_path}`}
              type="button"
              onClick={() => onSelect(run)}
              className={`w-full px-5 py-4 text-left transition hover:bg-[#f7fbf7] ${
                selected?.manifest_path === run.manifest_path ? "bg-[#e9f7f2] shadow-[inset_3px_0_0_#0f766e]" : ""
              }`}
            >
              <div className="truncate text-sm font-semibold text-zinc-950">{run.name}</div>
              <div className="mt-1 flex items-center gap-2 text-xs text-zinc-500">
                <span className="font-mono">{run.run_id}</span>
                <span>{run.child_run_count || 0} runs</span>
              </div>
            </button>
          ))
        )}
      </div>
    </Card>
  );
}

function FilterPanel({ query, onChange, onApply, onReset, strategyTypes, loading }) {
  return (
    <Card className="p-5">
      <div className="mb-4">
        <div className="text-base font-semibold tracking-[-0.02em] text-zinc-950">结果筛选</div>
        <div className="mt-1 text-xs leading-5 text-zinc-500">按名称、策略类型和排序方式查询 SQLite 结果索引</div>
      </div>
      <div className="space-y-3">
        <input
          value={query.search}
          onChange={(event) => onChange("search", event.target.value)}
          placeholder="搜索策略名、类型或变体 ID"
          className={fieldClassName}
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <select
            value={query.strategyType}
            onChange={(event) => onChange("strategyType", event.target.value)}
            className={fieldClassName}
          >
            <option value="">全部策略类型</option>
            {strategyTypes.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <select
            value={query.sortBy}
            onChange={(event) => onChange("sortBy", event.target.value)}
            className={fieldClassName}
          >
            <option value="generated_at">按时间排序</option>
            <option value="sharpe">按 Sharpe 排序</option>
            <option value="cumulative_return">按累计收益排序</option>
            <option value="max_drawdown">按回撤排序</option>
            <option value="final_equity">按最终权益排序</option>
          </select>
        </div>
        <select
          value={query.sortOrder}
          onChange={(event) => onChange("sortOrder", event.target.value)}
          className={fieldClassName}
        >
          <option value="desc">降序</option>
          <option value="asc">升序</option>
        </select>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={onApply}
            disabled={loading}
            className={primaryButtonClassName}
          >
            {loading ? "查询中..." : "应用筛选"}
          </button>
          <button
            type="button"
            onClick={onReset}
            disabled={loading}
            className={secondaryButtonClassName}
          >
            重置
          </button>
        </div>
      </div>
    </Card>
  );
}

function LineChart({ rows, yKey, height = 170, color = "#0f766e", label }) {
  const points = useMemo(() => {
    const values = rows.map((row) => Number(row[yKey])).filter((value) => Number.isFinite(value));
    if (rows.length === 0 || values.length === 0) {
      return "";
    }

    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    return rows
      .map((row, index) => {
        const value = Number(row[yKey]);
        const x = rows.length === 1 ? 0 : (index / (rows.length - 1)) * 1000;
        const y = height - ((value - min) / span) * (height - 18) - 9;
        return `${x},${Number.isFinite(y) ? y : height}`;
      })
      .join(" ");
  }, [rows, yKey, height]);

  if (!points) {
    return <div className="grid h-40 place-items-center rounded-[1.25rem] bg-[#f5f7f2] text-sm text-zinc-500">暂无 {label} 数据</div>;
  }

  return (
    <svg viewBox={`0 0 1000 ${height}`} className="h-full min-h-[150px] w-full overflow-visible">
      <line x1="0" x2="1000" y1={height - 1} y2={height - 1} stroke="#e4e4e7" />
      <polyline fill="none" stroke={color} strokeWidth="3" points={points} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function PriceTradeChart({ detail }) {
  const prices = detail?.artifacts?.prices ?? [];
  const trades = detail?.artifacts?.trades ?? [];
  const symbols = useMemo(() => Object.keys(prices[0] ?? {}).filter((key) => key !== "ts"), [prices]);
  const [symbol, setSymbol] = useState("");

  useEffect(() => {
    if (symbols.length === 0) {
      if (symbol) {
        setSymbol("");
      }
      return;
    }
    if (!symbols.includes(symbol)) {
      setSymbol(symbols[0]);
    }
  }, [symbol, symbols]);

  const xByTs = useMemo(() => {
    const map = new Map();
    prices.forEach((row, index) => {
      map.set(row.ts, prices.length === 1 ? 0 : (index / (prices.length - 1)) * 1000);
    });
    return map;
  }, [prices]);

  const yFor = useMemo(() => {
    const values = prices.map((row) => Number(row[symbol])).filter((value) => Number.isFinite(value));
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    return (value) => 250 - ((Number(value) - min) / span) * 228 - 11;
  }, [prices, symbol]);

  const selectedTrades = trades.filter((trade) => trade.symbol === symbol);

  return (
    <Card className="p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-zinc-950">价格与买卖点</div>
          <div className="text-xs text-zinc-500">权重变化会被转换为 buy / sell 标记</div>
        </div>
        <select
          value={symbol}
          onChange={(event) => setSymbol(event.target.value)}
          className={`${fieldClassName} max-w-[220px]`}
        >
          {symbols.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </div>
      <div className="relative h-[280px] rounded-[1.35rem] bg-[#f5f7f2] p-3 shadow-[inset_0_0_0_1px_rgba(24,24,27,0.06)]">
        <LineChart rows={prices} yKey={symbol} height={250} color="#18181b" label="price" />
        <svg viewBox="0 0 1000 250" className="pointer-events-none absolute inset-3 h-[250px] w-[calc(100%-1.5rem)] overflow-visible">
          {selectedTrades.map((trade, index) => {
            const x = xByTs.get(trade.ts);
            if (x === undefined || trade.price === null) {
              return null;
            }
            const y = yFor(trade.price);
            const isBuy = trade.side === "buy";
            return (
              <g key={`${trade.ts}-${index}`} transform={`translate(${x} ${y})`}>
                <circle r="7" fill={isBuy ? "#0f766e" : "#be123c"} opacity="0.92" />
                {isBuy ? (
                  <path d="M -4 2 L 0 -4 L 4 2" fill="none" stroke="white" strokeWidth="1.5" />
                ) : (
                  <path d="M -4 -2 L 0 4 L 4 -2" fill="none" stroke="white" strokeWidth="1.5" />
                )}
              </g>
            );
          })}
        </svg>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-zinc-600 sm:flex">
        <span className="inline-flex items-center gap-1">
          <ArrowUp size={14} className="text-teal-700" /> Buy / reduce short
        </span>
        <span className="inline-flex items-center gap-1">
          <ArrowDown size={14} className="text-rose-700" /> Sell / reduce long
        </span>
      </div>
    </Card>
  );
}

function DetailField({ label, value, mono = false }) {
  return (
    <div>
      <div className="text-zinc-500">{label}</div>
      <div className={`${mono ? "font-mono " : ""}text-zinc-900 break-all`}>{value === null || value === undefined || value === "" ? "-" : value}</div>
    </div>
  );
}

function ChildRunList({
  title,
  description,
  rows,
  onSelectRun,
  emptyLabel = "暂无子运行。",
  primaryMetricKey = "sharpe",
  primaryMetricLabel,
  secondaryMetricKey = "cumulative_return",
  secondaryMetricLabel,
  highlightManifestPath = "",
}) {
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-zinc-200 px-5 py-4">
        <div className="text-sm font-semibold text-zinc-950">{title}</div>
        <div className="text-xs text-zinc-500">{description}</div>
      </div>
      <div className="divide-y divide-zinc-100">
        {rows.length === 0 ? (
          <div className="px-5 py-6 text-sm text-zinc-500">{emptyLabel}</div>
        ) : (
          rows.map((row) => (
            <button
              key={`${row.run_id}-${row.manifest_path}`}
              type="button"
              onClick={() => onSelectRun(row)}
              className={`grid w-full grid-cols-[1fr_auto_auto] gap-3 px-5 py-3 text-left transition hover:bg-zinc-50 ${
                highlightManifestPath && row.manifest_path === highlightManifestPath ? "bg-teal-50/70" : ""
              }`}
            >
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-zinc-950">{row.strategy_name || row.name}</span>
                <span className="block truncate text-xs text-zinc-500">
                  {runTypeLabel(row)} · {row.run_id}
                </span>
              </span>
              <span className="text-right text-xs text-zinc-500">
                <span className="block">{primaryMetricLabel || metricLabel(primaryMetricKey)}</span>
                <span className="font-mono text-sm text-zinc-900">{formatMetricValue(metricOf(row, primaryMetricKey), primaryMetricKey)}</span>
              </span>
              <span className="text-right text-xs text-zinc-500">
                <span className="block">{secondaryMetricLabel || metricLabel(secondaryMetricKey)}</span>
                <span className="font-mono text-sm text-zinc-900">{formatMetricValue(metricOf(row, secondaryMetricKey), secondaryMetricKey)}</span>
              </span>
            </button>
          ))
        )}
      </div>
    </Card>
  );
}

function WinnerHighlight({ run, objectiveMetric, objectiveDirection, onSelectRun }) {
  if (!run) {
    return null;
  }

  return (
    <Card className="border-teal-200 bg-teal-50/70 p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-xs font-semibold tracking-[0.14em] text-teal-700">Winner</div>
          <div className="mt-2 text-lg font-semibold text-zinc-950">{run.strategy_name || run.name}</div>
          <div className="mt-2 text-xs text-zinc-600">
            {metricLabel(objectiveMetric)} ({objectiveDirection}) · {runTypeLabel(run)}
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-xs text-zinc-500">
            <span className="rounded border border-teal-200 bg-white px-2 py-1 font-mono">{run.run_id}</span>
            <span className="rounded border border-teal-200 bg-white px-2 py-1">
              {metricLabel(objectiveMetric)}: {formatMetricValue(metricOf(run, objectiveMetric), objectiveMetric)}
            </span>
            <span className="rounded border border-teal-200 bg-white px-2 py-1">
              Cumulative: {pct(metricOf(run, "cumulative_return"))}
            </span>
          </div>
        </div>
        <button
          type="button"
          onClick={() => onSelectRun(run)}
          className="dashboard-button-secondary border-teal-300 text-teal-800 hover:border-teal-500"
        >
          查看 workflow 详情
        </button>
      </div>
    </Card>
  );
}

function ComparisonMetricsTable({ rows, onSelectRun }) {
  const bestSharpe = rows.length > 0 ? [...rows].sort((left, right) => compareRunsByMetric(left, right, "sharpe", "max"))[0] : null;
  const bestReturn =
    rows.length > 0 ? [...rows].sort((left, right) => compareRunsByMetric(left, right, "cumulative_return", "max"))[0] : null;
  const bestDrawdown =
    rows.length > 0 ? [...rows].sort((left, right) => compareRunsByMetric(left, right, "max_drawdown", "min"))[0] : null;

  return (
    <Card className="overflow-hidden">
      <div className="border-b border-zinc-200 px-5 py-4">
        <div className="text-sm font-semibold text-zinc-950">指标对比</div>
        <div className="text-xs text-zinc-500">点击任意行可直接切换到对应 workflow 详情。</div>
      </div>
      {rows.length === 0 ? (
        <div className="px-5 py-6 text-sm text-zinc-500">暂无可展示的对比数据。</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-zinc-50 text-xs uppercase tracking-[0.12em] text-zinc-500">
              <tr>
                <th className="px-5 py-3 font-medium">Strategy</th>
                <th className="px-4 py-3 font-medium">Sharpe</th>
                <th className="px-4 py-3 font-medium">Cumulative</th>
                <th className="px-4 py-3 font-medium">Max DD</th>
                <th className="px-4 py-3 font-medium">Turnover</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {rows.map((row) => (
                <tr
                  key={`${row.run_id}-${row.manifest_path}`}
                  className="cursor-pointer transition hover:bg-zinc-50"
                  onClick={() => onSelectRun(row)}
                >
                  <td className="px-5 py-3">
                    <div className="font-medium text-zinc-950">{row.strategy_name || row.name}</div>
                    <div className="mt-1 text-xs text-zinc-500">{runTypeLabel(row)}</div>
                  </td>
                  <td className={`px-4 py-3 font-mono ${bestSharpe?.manifest_path === row.manifest_path ? "text-teal-700" : "text-zinc-900"}`}>
                    {fmt(metricOf(row, "sharpe"))}
                  </td>
                  <td className={`px-4 py-3 font-mono ${bestReturn?.manifest_path === row.manifest_path ? "text-teal-700" : "text-zinc-900"}`}>
                    {pct(metricOf(row, "cumulative_return"))}
                  </td>
                  <td className={`px-4 py-3 font-mono ${bestDrawdown?.manifest_path === row.manifest_path ? "text-teal-700" : "text-zinc-900"}`}>
                    {pct(metricOf(row, "max_drawdown"))}
                  </td>
                  <td className="px-4 py-3 font-mono text-zinc-900">{fmt(metricOf(row, "avg_turnover"))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function ExperimentDetail({ run, detailState, onSelectRun }) {
  if (!run) {
    return <EmptyState />;
  }
  if (detailState.loading) {
    return <Skeleton />;
  }
  if (detailState.error) {
    return <div className="rounded-[1.25rem] border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">{detailState.error}</div>;
  }

  const detail = detailState.detail;
  const experiment = detail?.manifest?.experiment ?? {};
  const winner = detail?.manifest?.winner ?? null;
  const children = detail?.children ?? [];
  const objectiveMetric = experiment.objective?.metric || "sharpe";
  const objectiveDirection = experiment.objective?.direction || "max";
  const rankedChildren = [...children].sort((left, right) => compareRunsByMetric(left, right, objectiveMetric, objectiveDirection));
  const winnerManifestPath = winner?.run_manifest_path;
  const winnerRun = winnerManifestPath
    ? children.find((child) => child.manifest_path === winnerManifestPath)
    : rankedChildren[0] || null;
  const description = experiment.description || run.primary_report_path || "批量实验结果与候选策略列表。";

  return (
    <div className="space-y-5">
      <Card className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs uppercase tracking-[0.14em] text-zinc-500">
              <ListChecks size={15} /> Experiment detail
            </div>
            <h1 className="mt-2 max-w-3xl text-2xl font-semibold tracking-tight text-zinc-950">{run.name}</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-600">{description}</p>
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-zinc-500">
              <span className="rounded border border-zinc-200 px-2 py-1 font-mono">{run.run_id}</span>
              <span className="rounded border border-zinc-200 px-2 py-1">{children.length} child runs</span>
              <span className="rounded border border-zinc-200 px-2 py-1">
                {metricLabel(objectiveMetric)} ({objectiveDirection})
              </span>
            </div>
          </div>
          <div className="rounded-[1rem] bg-[#f5f7f2] px-3 py-2 text-xs text-zinc-600 shadow-[inset_0_0_0_1px_rgba(24,24,27,0.06)]">
            <div className="text-zinc-500">Winner</div>
            <div className="font-mono text-zinc-900">{winnerRun?.strategy_name || winner?.strategy_name || "-"}</div>
          </div>
        </div>
      </Card>

      <WinnerHighlight
        run={winnerRun}
        objectiveMetric={objectiveMetric}
        objectiveDirection={objectiveDirection}
        onSelectRun={onSelectRun}
      />

      <div className="grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
        <Card className="p-5">
          <div className="text-sm font-semibold text-zinc-950">实验摘要</div>
          <div className="mt-4 grid gap-3 text-xs sm:grid-cols-2">
            <DetailField label="Objective" value={`${metricLabel(objectiveMetric)} (${objectiveDirection})`} />
            <DetailField label="Max workers" value={String(experiment.max_workers ?? "-")} />
            <DetailField label="Workflow count" value={String((detail?.manifest?.entries ?? []).length)} />
            <DetailField label="Winner strategy" value={winnerRun?.strategy_name || winner?.strategy_name || "-"} mono />
            <DetailField
              label="Winner metric"
              value={winnerRun ? formatMetricValue(metricOf(winnerRun, objectiveMetric), objectiveMetric) : "-"}
              mono
            />
            <DetailField label="Manifest" value={run.manifest_path} mono />
            <DetailField label="Primary report" value={run.primary_report_path || "-"} mono />
          </div>
        </Card>
        <ChildRunList
          title="子运行"
          description="按实验 objective 排序，点击任意候选策略可切换到对应 workflow 详情。"
          rows={rankedChildren}
          onSelectRun={onSelectRun}
          primaryMetricKey={objectiveMetric}
          primaryMetricLabel={metricLabel(objectiveMetric)}
          highlightManifestPath={winnerRun?.manifest_path || ""}
          emptyLabel="暂无可展示的子运行。"
        />
      </div>
    </div>
  );
}

function ComparisonDetail({ run, detailState, onSelectRun }) {
  if (!run) {
    return <EmptyState />;
  }
  if (detailState.loading) {
    return <Skeleton />;
  }
  if (detailState.error) {
    return <div className="rounded-[1.25rem] border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">{detailState.error}</div>;
  }

  const detail = detailState.detail;
  const comparison = detail?.manifest?.comparison ?? {};
  const children = detail?.children ?? [];
  const bestSharpeRun =
    children.length > 0 ? [...children].sort((left, right) => metricOf(right, "sharpe") - metricOf(left, "sharpe"))[0] : null;
  const bestReturnRun =
    children.length > 0
      ? [...children].sort((left, right) => metricOf(right, "cumulative_return") - metricOf(left, "cumulative_return"))[0]
      : null;
  const lowestDrawdownRun =
    children.length > 0
      ? [...children].sort((left, right) => metricOf(left, "max_drawdown") - metricOf(right, "max_drawdown"))[0]
      : null;

  return (
    <div className="space-y-5">
      <Card className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs uppercase tracking-[0.14em] text-zinc-500">
              <GitBranch size={15} /> Comparison detail
            </div>
            <h1 className="mt-2 max-w-3xl text-2xl font-semibold tracking-tight text-zinc-950">{run.name}</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-600">
              {comparison.description || "查看策略对比批次与可下钻的 workflow 结果。"}
            </p>
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-zinc-500">
              <span className="rounded border border-zinc-200 px-2 py-1 font-mono">{run.run_id}</span>
              <span className="rounded border border-zinc-200 px-2 py-1">{children.length} child runs</span>
            </div>
          </div>
          <div className="rounded-[1rem] bg-[#f5f7f2] px-3 py-2 text-xs text-zinc-600 shadow-[inset_0_0_0_1px_rgba(24,24,27,0.06)]">
            <div className="text-zinc-500">Best sharpe</div>
            <div className="font-mono text-zinc-900">{bestSharpeRun?.strategy_name || "-"}</div>
          </div>
        </div>
      </Card>

      <div className="grid gap-5 xl:grid-cols-3">
        <Card className="p-5">
          <div className="text-sm font-semibold text-zinc-950">Best Sharpe</div>
          <div className="mt-3 text-lg font-semibold text-zinc-950">{bestSharpeRun?.strategy_name || "-"}</div>
          <div className="mt-1 font-mono text-sm text-teal-700">
            {bestSharpeRun ? fmt(metricOf(bestSharpeRun, "sharpe")) : "-"}
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-sm font-semibold text-zinc-950">Best Return</div>
          <div className="mt-3 text-lg font-semibold text-zinc-950">{bestReturnRun?.strategy_name || "-"}</div>
          <div className="mt-1 font-mono text-sm text-teal-700">
            {bestReturnRun ? pct(metricOf(bestReturnRun, "cumulative_return")) : "-"}
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-sm font-semibold text-zinc-950">Lowest Drawdown</div>
          <div className="mt-3 text-lg font-semibold text-zinc-950">{lowestDrawdownRun?.strategy_name || "-"}</div>
          <div className="mt-1 font-mono text-sm text-teal-700">
            {lowestDrawdownRun ? pct(metricOf(lowestDrawdownRun, "max_drawdown")) : "-"}
          </div>
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <Card className="p-5">
          <div className="text-sm font-semibold text-zinc-950">对比摘要</div>
          <div className="mt-4 grid gap-3 text-xs sm:grid-cols-2">
            <DetailField label="Compared runs" value={String((detail?.manifest?.entries ?? []).length)} />
            <DetailField label="Best sharpe" value={bestSharpeRun ? `${bestSharpeRun.strategy_name} (${fmt(metricOf(bestSharpeRun, "sharpe"))})` : "-"} />
            <DetailField label="Best return" value={bestReturnRun ? `${bestReturnRun.strategy_name} (${pct(metricOf(bestReturnRun, "cumulative_return"))})` : "-"} />
            <DetailField label="Lowest drawdown" value={lowestDrawdownRun ? `${lowestDrawdownRun.strategy_name} (${pct(metricOf(lowestDrawdownRun, "max_drawdown"))})` : "-"} />
            <DetailField label="Manifest" value={run.manifest_path} mono />
            <DetailField label="Primary report" value={run.primary_report_path || "-"} mono />
          </div>
        </Card>
        <ChildRunList
          title="参与策略"
          description="按 Sharpe 排序，点击任意策略可直接下钻到 workflow 详情。"
          rows={[...children].sort((left, right) => compareRunsByMetric(left, right, "sharpe", "max"))}
          onSelectRun={onSelectRun}
          highlightManifestPath={bestSharpeRun?.manifest_path || ""}
          emptyLabel="暂无可展示的对比子运行。"
        />
      </div>

      <ComparisonMetricsTable rows={children} onSelectRun={onSelectRun} />
    </div>
  );
}

function RunDetail({ run, detailState }) {
  if (!run) {
    return <EmptyState />;
  }
  if (detailState.loading) {
    return <Skeleton />;
  }
  if (detailState.error) {
    return <div className="rounded-[1.25rem] border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">{detailState.error}</div>;
  }

  const detail = detailState.detail;
  const metrics = detail?.metrics?.backtest_metrics ?? run.backtest_metrics ?? {};
  const attribution = detail?.metrics?.backtest_attribution ?? run.backtest_attribution ?? {};
  const paperSummary = run.paper_summary ?? {};
  const artifactCount = Object.keys(run.structured_artifact_paths ?? {}).length;
  const tradeCount = detail?.artifacts?.trades?.length ?? 0;

  return (
    <div className="space-y-5">
      <Card className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs uppercase tracking-[0.14em] text-zinc-500">
              <Crosshair size={15} /> Selected run
            </div>
            <h1 className="mt-2 max-w-3xl text-2xl font-semibold tracking-tight text-zinc-950">{run.strategy_name || run.name}</h1>
            <div className="mt-2 flex flex-wrap gap-2 text-xs text-zinc-500">
              <span className="rounded border border-zinc-200 px-2 py-1 font-mono">{run.run_id}</span>
              <span className="rounded border border-zinc-200 px-2 py-1">{runTypeLabel(run)}</span>
              <span className="rounded border border-zinc-200 px-2 py-1">{artifactCount} artifacts</span>
            </div>
          </div>
          <div className="flex items-center gap-2 rounded-[1rem] bg-[#f5f7f2] px-3 py-2 text-xs text-zinc-600 shadow-[inset_0_0_0_1px_rgba(24,24,27,0.06)]">
            <GitBranch size={16} />
            <span className="font-mono">{run.git_sha ? run.git_sha.slice(0, 8) : "no git sha"}</span>
          </div>
        </div>
        <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Stat label="Sharpe" value={fmt(metrics.sharpe)} tone={metrics.sharpe > 0 ? "good" : "bad"} />
          <Stat label="Cumulative" value={pct(metrics.cumulative_return)} tone={metrics.cumulative_return > 0 ? "good" : "bad"} />
          <Stat label="Max DD" value={pct(metrics.max_drawdown)} tone="bad" />
          <Stat label="Turnover" value={fmt(metrics.avg_turnover)} />
        </div>
      </Card>

      {detail ? <PriceTradeChart detail={detail} /> : null}

      <div className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
        <Card className="p-5">
          <div className="mb-4 flex items-center gap-2">
            <ChartLineUp size={20} className="text-teal-700" />
            <div>
              <div className="text-sm font-semibold text-zinc-950">权益曲线</div>
              <div className="text-xs text-zinc-500">来自结构化 equity_curve artifact</div>
            </div>
          </div>
          <div className="h-[190px] rounded-[1.35rem] bg-[#f5f7f2] p-3 shadow-[inset_0_0_0_1px_rgba(24,24,27,0.06)]">
            <LineChart rows={detail?.artifacts?.equity_curve ?? []} yKey="equity" label="equity" />
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-sm font-semibold text-zinc-950">运行指纹</div>
          <div className="mt-4 space-y-3 text-xs">
            <div>
              <div className="text-zinc-500">Config hash</div>
              <div className="font-mono text-zinc-900">{run.config_hash || "-"}</div>
            </div>
            <div>
              <div className="text-zinc-500">Data snapshot</div>
              <div className="font-mono text-zinc-900">{run.data_snapshot_id || "-"}</div>
            </div>
            <div>
              <div className="text-zinc-500">Manifest</div>
              <div className="break-all font-mono text-zinc-900">{run.manifest_path}</div>
            </div>
          </div>
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card className="p-5">
          <div className="text-sm font-semibold text-zinc-950">回测归因</div>
          <div className="mt-4 grid gap-3 text-xs sm:grid-cols-2">
            <div>
              <div className="text-zinc-500">Gross return sum</div>
              <div className="font-mono text-zinc-900">{fmt(attribution.gross_return_sum)}</div>
            </div>
            <div>
              <div className="text-zinc-500">Trading cost sum</div>
              <div className="font-mono text-zinc-900">{fmt(attribution.trading_cost_sum)}</div>
            </div>
            <div>
              <div className="text-zinc-500">Funding cost sum</div>
              <div className="font-mono text-zinc-900">{fmt(attribution.funding_cost_sum)}</div>
            </div>
            <div>
              <div className="text-zinc-500">Trade rows</div>
              <div className="font-mono text-zinc-900">{fmt(tradeCount, "0")}</div>
            </div>
            <div>
              <div className="text-zinc-500">Top symbol</div>
              <div className="font-mono text-zinc-900">{attribution.top_symbol || "-"}</div>
            </div>
            <div>
              <div className="text-zinc-500">Worst symbol</div>
              <div className="font-mono text-zinc-900">{attribution.worst_symbol || "-"}</div>
            </div>
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-sm font-semibold text-zinc-950">模拟盘摘要</div>
          <div className="mt-4 grid gap-3 text-xs sm:grid-cols-2">
            <div>
              <div className="text-zinc-500">Final equity</div>
              <div className="font-mono text-zinc-900">{fmt(paperSummary.final_equity)}</div>
            </div>
            <div>
              <div className="text-zinc-500">Fill count</div>
              <div className="font-mono text-zinc-900">{fmt(paperSummary.fill_count, "0")}</div>
            </div>
            <div>
              <div className="text-zinc-500">Funding cashflow</div>
              <div className="font-mono text-zinc-900">{fmt(paperSummary.funding_cashflow)}</div>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

export default function DashboardClient({ initialRuns = [], initialError = "" }) {
  const { loading, error, runs, reload } = useRuns(initialRuns, initialError);
  const selectableRuns = runs.filter((run) => ["workflow_run", "experiment_run", "comparison_run"].includes(run.kind));
  const hasAnyRuns = selectableRuns.length > 0;
  const [selected, setSelected] = useState(() => pickInitialRun(initialRuns));
  const [query, setQuery] = useState({
    search: "",
    strategyType: "",
    sortBy: "generated_at",
    sortOrder: "desc",
  });

  const strategyTypes = useMemo(
    () =>
      [...new Set(runs.map((run) => run.strategy_type).filter(Boolean))].sort((left, right) => left.localeCompare(right)),
    [runs],
  );

  const updateQuery = useCallback((key, value) => {
    setQuery((current) => ({
      ...current,
      [key]: value,
    }));
  }, []);

  const applyFilters = useCallback(() => {
    reload(query);
  }, [query, reload]);

  const resetFilters = useCallback(() => {
    const next = {
      search: "",
      strategyType: "",
      sortBy: "generated_at",
      sortOrder: "desc",
    };
    setQuery(next);
    reload(next);
  }, [reload]);

  useEffect(() => {
    if (selectableRuns.length === 0) {
      if (selected !== null) {
        setSelected(null);
      }
      return;
    }

    const currentSelected = selected ? selectableRuns.find((run) => run.manifest_path === selected.manifest_path) : null;
    if (currentSelected) {
      if (currentSelected !== selected) {
        setSelected(currentSelected);
      }
      return;
    }

    setSelected(pickInitialRun(selectableRuns));
  }, [selected, selectableRuns]);

  const detailState = useSelectedDetail(selected);

  return (
    <div className="text-zinc-950">
      <div className="mx-auto max-w-[1440px] pb-12">
        <div className="mb-6">
          <Card className="border-zinc-200 bg-white bg-none text-zinc-950 shadow-[0_36px_110px_-74px_rgba(37,61,56,0.32)]">
            <div className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-teal-200/40 blur-3xl" />
            <div className="pointer-events-none absolute bottom-0 left-1/2 h-px w-2/3 -translate-x-1/2 bg-gradient-to-r from-transparent via-zinc-200 to-transparent" />
            <div className="grid gap-8 px-6 py-8 lg:grid-cols-[0.82fr_1.18fr] lg:items-end lg:px-8 xl:px-9">
              <div>
                <div className="dashboard-chip border-teal-200 bg-teal-50 text-teal-700">
                  <ListChecks size={14} />
                  Quant Strategy Lab
                </div>
                <h1 className="mt-5 max-w-3xl text-balance text-5xl font-semibold tracking-[-0.07em] text-zinc-950 md:text-6xl">
                  结果中心
                </h1>
                <p className="mt-4 max-w-[58ch] text-pretty text-sm leading-7 text-zinc-600">
                  从实验矩阵筛候选策略，再沿着 comparison、experiment 和 workflow 结果一路下钻到权益曲线、交易事件与运行指纹。
                </p>
                <div className="mt-5 flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={() => reload(query)}
                    disabled={loading}
                    className="inline-flex rounded-full border border-teal-200 bg-teal-600 px-4 py-2 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:border-teal-300 hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {loading ? "刷新中..." : "刷新结果索引"}
                  </button>
                  <span className="inline-flex items-center rounded-full border border-zinc-200 bg-zinc-50 px-4 py-2 text-sm text-zinc-600">
                    SQLite-powered dashboard
                  </span>
                </div>
              </div>
              <OverviewDeck runs={runs} selected={selected} />
            </div>
          </Card>
        </div>

        <div className="grid gap-6 xl:grid-cols-[380px_1fr]">
          <aside className="space-y-5 xl:sticky xl:top-5 xl:self-start">
            <FilterPanel
              query={query}
              onChange={updateQuery}
              onApply={applyFilters}
              onReset={resetFilters}
              strategyTypes={strategyTypes}
              loading={loading}
            />
            {loading ? <Skeleton /> : null}
            {error ? <div className="rounded-[1.25rem] border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">{error}</div> : null}
            {!loading && hasAnyRuns ? <Leaderboard runs={runs} selected={selected} onSelect={setSelected} /> : null}
            {!loading && hasAnyRuns ? <Experiments runs={runs} selected={selected} onSelect={setSelected} /> : null}
            {!loading && hasAnyRuns ? <Comparisons runs={runs} selected={selected} onSelect={setSelected} /> : null}
          </aside>
          <section className="min-w-0">
            {!loading && !selected ? <EmptyState /> : null}
            {selected?.kind === "workflow_run" ? <RunDetail run={selected} detailState={detailState} /> : null}
            {selected?.kind === "experiment_run" ? (
              <ExperimentDetail run={selected} detailState={detailState} onSelectRun={setSelected} />
            ) : null}
            {selected?.kind === "comparison_run" ? (
              <ComparisonDetail run={selected} detailState={detailState} onSelectRun={setSelected} />
            ) : null}
          </section>
        </div>
      </div>
    </div>
  );
}
