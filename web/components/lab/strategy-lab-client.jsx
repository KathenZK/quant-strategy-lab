"use client";

import { useEffect, useMemo, useState } from "react";

import { fetchStrategyLabAppJson, STRATEGY_LAB_ENDPOINTS } from "../../lib/strategy-lab-api";

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

function ExperimentDraft({ selected, yamlDraft, onYamlChange, onCreateJob, submitting }) {
  const universe = Array.isArray(selected.default_universe) ? selected.default_universe : [];

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
          {submitting ? "创建中..." : "用 YAML 创建回测任务"}
        </button>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4">
          <div className="text-xs text-zinc-500">YAML 文件</div>
          <div className="mt-2 break-all font-mono text-sm font-semibold text-zinc-950">{selected.path}</div>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4">
          <div className="text-xs text-zinc-500">策略 / 周期</div>
          <div className="mt-2 font-mono text-sm font-semibold text-zinc-950">
            {selected.strategy_type} / {selected.default_timeframe}
          </div>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4">
          <div className="text-xs text-zinc-500">Universe</div>
          <div className="mt-2 text-sm font-semibold text-zinc-950">{universe.join(" / ")}</div>
        </div>
      </div>

      <div className="mt-5 rounded-lg border border-zinc-200 bg-zinc-50 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">Workflow YAML</div>
            <p className="mt-2 text-xs leading-5 text-zinc-500">这里编辑的是完整 workflow。提交时后端会用同一套 YAML loader 校验。</p>
          </div>
          <div className="rounded border border-zinc-200 bg-white px-2 py-1 text-[11px] text-zinc-500">source of truth</div>
        </div>
        <textarea
          value={yamlDraft}
          onChange={(event) => onYamlChange(event.target.value)}
          spellCheck={false}
          className="mt-4 min-h-[560px] w-full resize-y rounded-lg border border-zinc-200 bg-white p-4 font-mono text-sm leading-6 text-zinc-950 outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
        />
      </div>
    </>
  );
}

function JobSummary({ job }) {
  if (!job) {
    return null;
  }

  const failed = job.status === "failed";
  const completed = job.status === "completed";
  const panelClass = failed
    ? "border-rose-200 bg-rose-50"
    : completed
      ? "border-emerald-200 bg-emerald-50"
      : "border-amber-200 bg-amber-50";
  const titleClass = failed ? "text-rose-800" : completed ? "text-emerald-800" : "text-amber-800";
  const labelClass = failed ? "text-rose-700/70" : completed ? "text-emerald-700/70" : "text-amber-700/70";
  const messageClass = failed ? "text-rose-800/75" : completed ? "text-emerald-800/75" : "text-amber-800/75";

  return (
    <div className={`mt-5 rounded-lg border p-4 ${panelClass}`}>
      <div className={`text-sm font-semibold ${titleClass}`}>{failed ? "回测任务失败" : completed ? "回测任务已完成" : "回测任务已创建"}</div>
      <div className="mt-3 grid gap-3 md:grid-cols-3">
        <div>
          <div className={`text-xs ${labelClass}`}>Job ID</div>
          <div className="mt-1 font-mono text-sm text-zinc-950">{job.id}</div>
        </div>
        <div>
          <div className={`text-xs ${labelClass}`}>Status</div>
          <div className="mt-1 font-mono text-sm text-zinc-950">{job.status}</div>
        </div>
        <div>
          <div className={`text-xs ${labelClass}`}>{completed ? "Run ID" : "Snapshot"}</div>
          <div className="mt-1 font-mono text-sm text-zinc-950">{completed ? job.run_id : job.data_snapshot_id}</div>
        </div>
        {job.backtest_report_path ? (
          <div className="md:col-span-3">
            <div className={`text-xs ${labelClass}`}>Backtest report</div>
            <div className="mt-1 break-all font-mono text-xs text-zinc-950">{job.backtest_report_path}</div>
          </div>
        ) : null}
        {job.error ? (
          <div className="md:col-span-3">
            <div className={`text-xs ${labelClass}`}>Error</div>
            <div className="mt-1 break-all font-mono text-xs text-zinc-950">{job.error}</div>
          </div>
        ) : null}
      </div>
      <p className={`mt-3 text-xs leading-5 ${messageClass}`}>{job.next_step}</p>
    </div>
  );
}

export default function StrategyLabClient({ initialTemplates = [] }) {
  const [templates] = useState(initialTemplates);
  const [selectedId, setSelectedId] = useState(initialTemplates[0]?.id ?? "");
  const [yamlDraft, setYamlDraft] = useState(initialTemplates[0]?.workflow_yaml ?? "");
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const selected = useMemo(() => templates.find((template) => template.id === selectedId) ?? templates[0], [selectedId, templates]);

  useEffect(() => {
    setYamlDraft(selected?.workflow_yaml ?? "");
    setJob(null);
    setError("");
  }, [selected?.id, selected?.workflow_yaml]);

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
          workflow_yaml: yamlDraft,
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
              yamlDraft={yamlDraft}
              onYamlChange={setYamlDraft}
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
