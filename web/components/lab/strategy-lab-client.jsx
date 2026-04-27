"use client";

import { useMemo, useState } from "react";

import { fetchStrategyLabAppJson, STRATEGY_LAB_ENDPOINTS } from "../../lib/strategy-lab-api";

const sourceOptions = [
  { value: "binance", label: "Binance" },
  { value: "okx", label: "OKX" },
];

function TemplatePicker({ templates, selectedId, onSelect }) {
  return (
    <section className="lab-card p-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">Strategy templates</div>
      <h1 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-zinc-950">策略实验室</h1>
      <p className="mt-3 text-sm leading-6 text-zinc-600">先用模板化策略把 Web 创建、参数、数据快照和回测任务链路打通。</p>

      <div className="mt-5 space-y-3">
        {templates.map((template) => {
          const active = template.id === selectedId;
          return (
            <button
              key={template.id}
              type="button"
              onClick={() => onSelect(template.id)}
              className={`w-full rounded-lg border p-3 text-left ${
                active ? "border-blue-200 bg-blue-50" : "border-zinc-200 bg-zinc-50 hover:bg-white"
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="font-semibold text-zinc-950">{template.name}</div>
                <span className="rounded border border-zinc-200 bg-white px-2 py-1 text-[11px] text-zinc-500">{template.category}</span>
              </div>
              <div className="mt-2 text-xs leading-5 text-zinc-500">{template.description}</div>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function ExperimentDraft({ selected, source, onSourceChange, onCreateJob, submitting }) {
  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">Experiment draft</div>
          <h2 className="mt-2 text-2xl font-semibold text-zinc-950">{selected.name}</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-600">{selected.description}</p>
        </div>
        <button
          type="button"
          onClick={onCreateJob}
          disabled={submitting}
          className="rounded-md bg-[#1f6feb] px-4 py-2 text-sm font-semibold text-white hover:bg-[#185abc] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? "创建中..." : "创建回测任务"}
        </button>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <label className="rounded-lg border border-zinc-200 bg-zinc-50 p-4">
          <span className="text-xs text-zinc-500">数据源</span>
          <select
            value={source}
            onChange={(event) => onSourceChange(event.target.value)}
            className="mt-2 w-full rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-950"
          >
            {sourceOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4">
          <div className="text-xs text-zinc-500">周期</div>
          <div className="mt-2 font-mono text-lg font-semibold text-zinc-950">{selected.default_timeframe}</div>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4">
          <div className="text-xs text-zinc-500">Universe</div>
          <div className="mt-2 text-sm font-semibold text-zinc-950">{selected.default_universe.join(" / ")}</div>
        </div>
      </div>

      <div className="mt-5 rounded-lg border border-zinc-200 bg-zinc-50 p-4">
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">Parameters</div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {selected.parameters.map((parameter) => (
            <div key={parameter.key} className="rounded-lg border border-zinc-200 bg-white p-3">
              <div className="text-xs text-zinc-500">{parameter.label}</div>
              <div className="mt-1 font-mono text-lg font-semibold tabular-nums text-zinc-950">{parameter.default}</div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function JobSummary({ job }) {
  if (!job) {
    return null;
  }

  return (
    <div className="mt-5 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
      <div className="text-sm font-semibold text-emerald-800">回测任务已创建</div>
      <div className="mt-3 grid gap-3 md:grid-cols-3">
        <div>
          <div className="text-xs text-emerald-700/70">Job ID</div>
          <div className="mt-1 font-mono text-sm text-zinc-950">{job.id}</div>
        </div>
        <div>
          <div className="text-xs text-emerald-700/70">Status</div>
          <div className="mt-1 font-mono text-sm text-zinc-950">{job.status}</div>
        </div>
        <div>
          <div className="text-xs text-emerald-700/70">Snapshot</div>
          <div className="mt-1 font-mono text-sm text-zinc-950">{job.data_snapshot_id}</div>
        </div>
      </div>
      <p className="mt-3 text-xs leading-5 text-emerald-800/75">{job.next_step}</p>
    </div>
  );
}

export default function StrategyLabClient({ initialTemplates = [] }) {
  const [templates] = useState(initialTemplates);
  const [selectedId, setSelectedId] = useState(initialTemplates[0]?.id ?? "");
  const [source, setSource] = useState("binance");
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const selected = useMemo(() => templates.find((template) => template.id === selectedId) ?? templates[0], [selectedId, templates]);

  async function createJob() {
    if (!selected) {
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const payload = await fetchStrategyLabAppJson(STRATEGY_LAB_ENDPOINTS.labBacktests, {
        method: "POST",
        body: {
          template_id: selected.id,
          source,
          timeframe: selected.default_timeframe,
          universe: selected.default_universe,
        },
      });
      setJob(payload.job);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "创建回测任务失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[380px_1fr]">
      <TemplatePicker templates={templates} selectedId={selected?.id ?? selectedId} onSelect={setSelectedId} />

      <section className="lab-card p-4">
        {selected ? (
          <>
            <ExperimentDraft
              selected={selected}
              source={source}
              onSourceChange={setSource}
              onCreateJob={createJob}
              submitting={submitting}
            />

            {error ? <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</div> : null}
            <JobSummary job={job} />
          </>
        ) : (
          <div className="rounded-lg border border-dashed border-zinc-300 p-8 text-zinc-500">暂无策略模板，请确认 Strategy Lab API 是否启动。</div>
        )}
      </section>
    </div>
  );
}
