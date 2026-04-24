"use client";

import { useEffect, useMemo, useState } from "react";
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

async function getJson(url) {
  const response = await fetch(url, {
    cache: "no-store",
    headers: {
      accept: "application/json",
    },
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

function metricOf(run, key) {
  return run?.backtest_metrics?.[key] ?? 0;
}

function pickBestWorkflowRun(runs) {
  const workflowRuns = runs.filter((run) => run.kind === "workflow_run");
  if (workflowRuns.length === 0) {
    return null;
  }
  return [...workflowRuns].sort((a, b) => metricOf(b, "sharpe") - metricOf(a, "sharpe"))[0];
}

function useRuns(initialRuns = [], initialError = "") {
  const [state, setState] = useState({
    loading: false,
    error: initialError,
    runs: initialRuns,
  });

  useEffect(() => {
    let cancelled = false;
    getJson("/api/runs")
      .then((data) => {
        if (!cancelled) {
          setState({
            loading: false,
            error: "",
            runs: data.runs ?? [],
          });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setState((current) => ({
            loading: false,
            error: error.message,
            runs: current.runs,
          }));
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}

function useRunDetail(run) {
  const [state, setState] = useState({ loading: false, error: "", detail: null });

  useEffect(() => {
    if (!run?.manifest_path || run.kind !== "workflow_run") {
      setState({ loading: false, error: "", detail: null });
      return;
    }

    let cancelled = false;
    setState({ loading: true, error: "", detail: null });
    getJson(`/api/run-detail?manifest_path=${encodeURIComponent(run.manifest_path)}`)
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
    <section className={`rounded-lg border border-zinc-200 bg-white shadow-[0_18px_40px_-28px_rgba(24,24,27,0.35)] ${className}`}>
      {children}
    </section>
  );
}

function Skeleton() {
  return (
    <div className="space-y-3 p-5">
      <div className="h-4 w-2/5 animate-pulse rounded bg-zinc-200" />
      <div className="h-24 animate-pulse rounded-md bg-zinc-100" />
      <div className="h-4 w-4/5 animate-pulse rounded bg-zinc-200" />
    </div>
  );
}

function EmptyState() {
  return (
    <div className="grid min-h-[420px] place-items-center rounded-lg border border-dashed border-zinc-300 bg-zinc-50 p-8 text-center">
      <div>
        <Database className="mx-auto mb-4 text-zinc-500" size={32} weight="duotone" />
        <h2 className="text-xl font-semibold text-zinc-900">还没有可展示的运行结果</h2>
        <p className="mt-2 max-w-xl text-sm leading-6 text-zinc-600">
          先运行一次策略或实验，dashboard 会读取 reports registry，并自动展示排名、权益曲线、价格线和买卖点。
        </p>
      </div>
    </div>
  );
}

function Stat({ label, value, tone = "neutral" }) {
  const color = tone === "good" ? "text-teal-700" : tone === "bad" ? "text-rose-700" : "text-zinc-950";

  return (
    <div className="border-t border-zinc-200 pt-3">
      <div className="text-xs uppercase tracking-[0.12em] text-zinc-500">{label}</div>
      <div className={`mt-1 font-mono text-2xl font-semibold ${color}`}>{value}</div>
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
      <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-4">
        <div>
          <div className="text-sm font-semibold text-zinc-950">策略排行</div>
          <div className="text-xs text-zinc-500">按 Sharpe 自动排序</div>
        </div>
        <Trophy size={22} className="text-teal-700" weight="duotone" />
      </div>
      <div className="divide-y divide-zinc-100">
        {workflowRuns.slice(0, 12).map((run, index) => (
          <button
            key={`${run.run_id}-${run.manifest_path}`}
            type="button"
            onClick={() => onSelect(run)}
            className={`grid w-full grid-cols-[2rem_1fr_auto] items-center gap-3 px-5 py-3 text-left transition hover:bg-zinc-50 active:translate-y-px ${
              selected?.manifest_path === run.manifest_path ? "bg-teal-50" : ""
            }`}
          >
            <span className="font-mono text-xs text-zinc-500">{String(index + 1).padStart(2, "0")}</span>
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium text-zinc-950">{run.strategy_name || run.name}</span>
              <span className="block truncate text-xs text-zinc-500">{run.variant_id || run.signal_type}</span>
            </span>
            <span className="font-mono text-sm font-semibold text-zinc-900">{fmt(metricOf(run, "sharpe"))}</span>
          </button>
        ))}
      </div>
    </Card>
  );
}

function Experiments({ runs }) {
  const experiments = runs.filter((run) => run.kind === "experiment_run").slice(0, 8);

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center gap-2 border-b border-zinc-200 px-5 py-4">
        <ListChecks size={20} className="text-zinc-700" />
        <div>
          <div className="text-sm font-semibold text-zinc-950">实验批次</div>
          <div className="text-xs text-zinc-500">包含 sweep 与自动选优结果</div>
        </div>
      </div>
      <div className="divide-y divide-zinc-100">
        {experiments.length === 0 ? (
          <div className="px-5 py-6 text-sm text-zinc-500">暂无 experiment run。</div>
        ) : (
          experiments.map((run) => (
            <div key={`${run.run_id}-${run.manifest_path}`} className="px-5 py-3">
              <div className="truncate text-sm font-medium text-zinc-950">{run.name}</div>
              <div className="mt-1 flex items-center gap-2 text-xs text-zinc-500">
                <span className="font-mono">{run.run_id}</span>
              </div>
            </div>
          ))
        )}
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
    return <div className="grid h-40 place-items-center rounded-md bg-zinc-50 text-sm text-zinc-500">暂无 {label} 数据</div>;
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
          className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-teal-700"
        >
          {symbols.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </div>
      <div className="relative h-[280px] rounded-md border border-zinc-200 bg-zinc-50 p-3">
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

function RunDetail({ run, detailState }) {
  if (!run) {
    return <EmptyState />;
  }
  if (detailState.loading) {
    return <Skeleton />;
  }
  if (detailState.error) {
    return <div className="rounded-lg border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">{detailState.error}</div>;
  }

  const detail = detailState.detail;
  const metrics = run.backtest_metrics ?? {};
  const artifactCount = Object.keys(run.structured_artifact_paths ?? {}).length;

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
              <span className="rounded border border-zinc-200 px-2 py-1">{run.variant_id || run.signal_type}</span>
              <span className="rounded border border-zinc-200 px-2 py-1">{artifactCount} artifacts</span>
            </div>
          </div>
          <div className="flex items-center gap-2 rounded-md border border-zinc-200 px-3 py-2 text-xs text-zinc-600">
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
          <div className="h-[190px] rounded-md bg-zinc-50 p-3">
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
    </div>
  );
}

export default function DashboardClient({ initialRuns = [], initialError = "" }) {
  const { loading, error, runs } = useRuns(initialRuns, initialError);
  const hasAnyRuns = runs.length > 0;
  const workflowRuns = runs.filter((run) => run.kind === "workflow_run");
  const [selected, setSelected] = useState(() => pickBestWorkflowRun(initialRuns));

  useEffect(() => {
    if (workflowRuns.length === 0) {
      if (selected !== null) {
        setSelected(null);
      }
      return;
    }

    const currentSelected = selected ? workflowRuns.find((run) => run.manifest_path === selected.manifest_path) : null;
    if (currentSelected) {
      if (currentSelected !== selected) {
        setSelected(currentSelected);
      }
      return;
    }

    setSelected(pickBestWorkflowRun(workflowRuns));
  }, [selected, workflowRuns]);

  const detailState = useRunDetail(selected);

  return (
    <main className="min-h-[100dvh] bg-[#f7f7f5] text-zinc-950">
      <div className="mx-auto grid max-w-[1500px] gap-6 px-4 py-5 md:px-6 xl:grid-cols-[390px_1fr]">
        <aside className="space-y-5 xl:sticky xl:top-5 xl:self-start">
          <div className="rounded-lg border border-zinc-200 bg-zinc-950 p-5 text-white">
            <div className="text-xs uppercase tracking-[0.16em] text-zinc-400">Quant Strategy Lab</div>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight">策略实验台</h1>
            <p className="mt-3 text-sm leading-6 text-zinc-300">从实验矩阵里选出候选策略，再下钻到买卖点、权益曲线和运行指纹。</p>
          </div>
          {loading ? <Skeleton /> : null}
          {error ? <div className="rounded-lg border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">{error}</div> : null}
          {!loading && hasAnyRuns ? <Leaderboard runs={runs} selected={selected} onSelect={setSelected} /> : null}
          {!loading && hasAnyRuns ? <Experiments runs={runs} /> : null}
        </aside>
        <section>{!loading && workflowRuns.length === 0 ? <EmptyState /> : <RunDetail run={selected} detailState={detailState} />}</section>
      </div>
    </main>
  );
}
