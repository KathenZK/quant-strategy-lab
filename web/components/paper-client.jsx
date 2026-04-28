"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { PlayCircle, Sparkle } from "@phosphor-icons/react";

import RunDetailPanel from "./run-detail-panel";
import { buildLabRunHref, formatDate, formatMetric, metricOf, runIdentity, shortHash, strategyLabel } from "../lib/strategy-workbench";

const candidateStorageKey = "quant-strategy-lab-candidates";

function readCandidateMap() {
  if (typeof window === "undefined") {
    return {};
  }
  try {
    return JSON.parse(window.localStorage.getItem(candidateStorageKey) || "{}");
  } catch {
    return {};
  }
}

function RunCard({ run, selected, badge, onSelect }) {
  return (
    <button
      type="button"
      onClick={() => onSelect(run)}
      className={`w-full rounded-lg border p-4 text-left ${
        selected
          ? "border-teal-200 bg-teal-50 dark:border-teal-400/30 dark:bg-teal-950/30"
          : "border-zinc-200 bg-white hover:bg-zinc-50 dark:border-slate-800 dark:bg-[#111722] dark:hover:bg-slate-900/70"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-zinc-950 dark:text-zinc-100">{run.strategy_name || strategyLabel(run)}</div>
          <div className="mt-1 font-mono text-xs text-zinc-500 dark:text-slate-500">{shortHash(run.run_id)} · {formatDate(run.generated_at)}</div>
        </div>
        <span className="rounded border border-zinc-200 bg-zinc-50 px-2 py-1 text-[11px] text-zinc-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">{badge}</span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
        <div>
          <div className="text-zinc-500">Sharpe</div>
          <div className="mt-1 font-mono font-semibold text-zinc-950 dark:text-zinc-100">{formatMetric(metricOf(run, "sharpe"))}</div>
        </div>
        <div>
          <div className="text-zinc-500">Final equity</div>
          <div className="mt-1 font-mono font-semibold text-zinc-950 dark:text-zinc-100">{formatMetric(run.paper_summary?.final_equity)}</div>
        </div>
      </div>
    </button>
  );
}

export default function PaperClient({ initialRuns = [] }) {
  const [candidateMap, setCandidateMap] = useState({});
  const [selectedRun, setSelectedRun] = useState(null);

  const candidateRuns = useMemo(() => {
    const ids = new Set(Object.values(candidateMap).filter(Boolean));
    return initialRuns.filter((run) => ids.has(runIdentity(run)));
  }, [candidateMap, initialRuns]);

  const paperRuns = useMemo(
    () => initialRuns.filter((run) => run.paper_report_path || Object.keys(run.paper_summary ?? {}).length > 0),
    [initialRuns],
  );

  useEffect(() => {
    setCandidateMap(readCandidateMap());
  }, []);

  useEffect(() => {
    setSelectedRun((current) => current ?? candidateRuns[0] ?? paperRuns[0] ?? null);
  }, [candidateRuns, paperRuns]);

  return (
    <div className="space-y-5">
      <section className="lab-card p-5">
        <div className="inline-flex items-center gap-2 rounded-md border border-teal-200 bg-teal-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-teal-700 dark:border-teal-400/30 dark:bg-teal-950/30 dark:text-teal-200">
          <PlayCircle size={14} />
          Paper trading
        </div>
        <h1 className="mt-4 text-4xl font-semibold tracking-[-0.06em] text-zinc-950 dark:text-zinc-100">模拟盘</h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-600 dark:text-slate-400">
          这里先汇总“策略工作台”里设为候选的参数版本，以及 workflow 已经产出的模拟盘摘要。后续可以在这个入口扩展成独立的长期模拟盘会话。
        </p>
      </section>

      <div className="grid gap-5 xl:grid-cols-[390px_1fr]">
        <aside className="space-y-5">
          <section className="lab-card p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-zinc-950 dark:text-zinc-100">
              <Sparkle size={18} />
              候选策略
            </div>
            <div className="mt-4 space-y-3">
              {candidateRuns.length ? (
                candidateRuns.map((run) => (
                  <RunCard key={runIdentity(run)} run={run} selected={runIdentity(run) === runIdentity(selectedRun)} badge="候选" onSelect={setSelectedRun} />
                ))
              ) : (
                <div className="rounded-lg border border-dashed border-zinc-300 bg-zinc-50 p-5 text-sm leading-6 text-zinc-500 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-400">
                  暂无候选。回到策略工作台，挑一条回测结果设为模拟盘候选。
                </div>
              )}
            </div>
          </section>

          <section className="lab-card p-4">
            <div className="text-sm font-semibold text-zinc-950 dark:text-zinc-100">已有模拟盘产出</div>
            <div className="mt-4 space-y-3">
              {paperRuns.length ? (
                paperRuns.map((run) => (
                  <RunCard key={runIdentity(run)} run={run} selected={runIdentity(run) === runIdentity(selectedRun)} badge="Paper" onSelect={setSelectedRun} />
                ))
              ) : (
                <div className="rounded-lg border border-dashed border-zinc-300 bg-zinc-50 p-5 text-sm leading-6 text-zinc-500 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-400">
                  还没有带模拟盘摘要的 Run。确认 workflow 中 `run_paper_trade` 开启后再执行回测。
                </div>
              )}
            </div>
          </section>
        </aside>

        <main className="space-y-4">
          <RunDetailPanel run={selectedRun} candidate={candidateRuns.some((run) => runIdentity(run) === runIdentity(selectedRun))} />
          {selectedRun ? (
            <Link href={buildLabRunHref(selectedRun)} className="inline-flex rounded-md border border-zinc-200 bg-white px-3 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200">
              回到策略工作台
            </Link>
          ) : null}
        </main>
      </div>
    </div>
  );
}
