# HYPE-EMA-X Research Scripts

This directory contains one-off reproduction, audit, search, and report-generation scripts for the `HYPE-EMA-X` family.

Rules:

- Keep scripts here when they only serve this strategy family.
- Write durable Markdown conclusions back to this family directory.
- Write retained JSON, CSV, and HTML outputs to `../artifacts/`.
- Write durable audit/diagnostic Markdown to `../diagnostics/`.
- Write ablation conclusions to `../ablations/`.
- Write clean promoted specs to `../specs/`.
- Promote code to `src/strategy_lab/` only if it becomes reusable data infrastructure or a narrow dataset exporter.

## Current scripts

- `research_hype_ema_x_v18_retest.py`：按 `HYPE-EMA-X-V18` 干净规格复测台账切片，并生成最近窗口与滚动窗口结果。
